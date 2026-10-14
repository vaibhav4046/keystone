"""Incident feedback: score the engine's own recall against production reality.

The problem this solves
-----------------------
Every governance engine can say "this change has a blast radius of 37". Almost
none can say whether that number was ever *right*. A gate that always reports a
huge blast radius looks safe and learns nothing, and a gate that reports a small
one looks efficient until the day it misses.

Keystone already records a blast-radius set at review time, in the ledger, next to
the human decision. This module closes the loop: when an incident names the
symbols that actually broke, compare the recorded prediction against the observed
outcome and report the engine's precision, recall and, most usefully, which
symbols it *missed*.

Why the missed set is the point
-------------------------------
`hit` and `overpredicted` are metrics. `missed` is a safety finding: a symbol that
broke and that no recorded decision had predicted is exactly the dependency the
precedent store is missing. Those rows are what should be promoted into the
memory next time, which is how the store stops being a log and starts being
learning.

Honest limits, stated rather than hidden
----------------------------------------
This is set coverage, not causality. An observed symbol appearing in the
prediction does not prove the prediction "caught" it, and a symbol missing from
the prediction may have broken for an unrelated reason. What is claimed here is
narrow and true: *did the recorded prediction cover what actually broke*. The
module reports that and nothing stronger.

Independence is also assumed rather than proven: it trusts that the incident's
observed symbol set is correct, because that set is supplied by whoever triaged
the incident. A wrong observed set produces a wrong score, not a wrong verdict
about Keystone.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterable, Optional

# Verdicts, most alarming first.
UNDERSTATED = "PREDICTION_UNDERSTATED"   # broke something nobody predicted
HELD = "PREDICTION_HELD"                 # the recorded set covered the outcome
OVERSTATED = "PREDICTION_OVERSTATED"     # warned about things that stayed fine
NO_BASELINE = "NO_BASELINE"               # no recorded decision to score against


@dataclass
class Incident:
    """One production incident, as triaged."""
    id: str
    observed: list = field(default_factory=list)   # symbols that actually broke
    change_id: str = ""                            # links back to a ledger decision
    summary: str = ""

    def observed_set(self) -> set:
        return {s for s in (self.observed or []) if s}


@dataclass
class RecallReport:
    """How one recorded prediction held up against one real outcome."""
    incident_id: str
    change_id: str
    predicted: list
    observed: list
    hit: list
    missed: list            # observed but never predicted  <- the safety finding
    overpredicted: list     # predicted but never observed
    verdict: str

    @property
    def precision(self) -> float:
        p = len(self.predicted)
        return (len(self.hit) / p) if p else 0.0

    @property
    def recall(self) -> float:
        o = len(self.observed)
        return (len(self.hit) / o) if o else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return (2 * p * r / (p + r)) if (p + r) else 0.0

    def to_dict(self) -> dict:
        return {
            "incident_id": self.incident_id,
            "change_id": self.change_id,
            "verdict": self.verdict,
            "counts": {
                "predicted": len(self.predicted),
                "observed": len(self.observed),
                "hit": len(self.hit),
                "missed": len(self.missed),
                "overpredicted": len(self.overpredicted),
            },
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "missed": sorted(self.missed),
            "overpredicted": sorted(self.overpredicted),
        }


def _row_symbols(row: dict) -> set:
    """Extract the symbol-identity set from a ledger row.

    Name-bearing fields are preferred over ``blast_radius_set`` on purpose. The
    ledger stores the blast set as DuckDB row ids, and those ids are assigned at
    index time -- they are not stable across a re-index or a different machine,
    so comparing them against an incident's symbol names would report a total
    miss every time. This is the same reasoning behind
    ``core.impact.blast_radius_signature_fqn``: precedent has to key on what the
    change touches, not on volatile ids.

    The id-based field is still accepted as a last resort, because a scorer that
    returns an empty set for a row it cannot interpret would report NO_BASELINE
    and hide a real regression.
    """
    for key in ("target_symbols", "affected_fqns", "symbols", "blast_radius_set"):
        v = row.get(key)
        if not v:
            continue
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except (ValueError, TypeError):
                v = [s for s in (x.strip() for x in v.split(",")) if s]
        try:
            return {str(x) for x in v if str(x)}
        except TypeError:
            continue
    return set()


def _match_key(row: dict) -> str:
    for key in ("change_id", "change", "id"):
        v = row.get(key)
        if v:
            return str(v)
    return ""


def _row_decision(row: dict) -> str:
    for key in ("decision", "action", "verdict"):
        v = row.get(key)
        if v:
            return str(v).upper()
    return ""


def find_baseline(ledger, incident: Incident) -> Optional[dict]:
    """Locate the recorded decision this incident should be scored against.

    Prefers an exact change_id match. Falls back to the most recent recorded
    APPROVE for the same target, so an incident that was never tagged with a
    change id still gets scored rather than silently dropped.
    """
    rows = ledger.rows() if hasattr(ledger, "rows") else []
    if incident.change_id:
        for r in rows:
            if _match_key(r) == incident.change_id:
                return r
    observed = incident.observed_set()
    best = None
    for r in rows:
        if "APPROVE" not in _row_decision(r):
            continue
        syms = _row_symbols(r)
        if syms & observed:
            if best is None:
                best = r
    return best


def score(ledger, incident: Incident) -> RecallReport:
    """Score one incident against the recorded prediction.

    A missing baseline is reported as NO_BASELINE with empty sets, never as a
    clean bill of health: "we could not check" and "we checked and were right"
    must never look the same in a safety report.
    """
    obs = incident.observed_set()
    row = find_baseline(ledger, incident)

    if row is None:
        return RecallReport(incident.id, incident.change_id, [], sorted(obs), [],
                            sorted(obs), [], NO_BASELINE)

    pred = _row_symbols(row)
    hit = pred & obs
    missed = obs - pred          # broke, and nothing predicted it
    over = pred - obs

    if missed:
        verdict = UNDERSTATED
    elif over and not hit:
        verdict = OVERSTATED
    elif hit:
        verdict = HELD
    else:
        verdict = OVERSTATED

    return RecallReport(
        incident_id=incident.id,
        change_id=_match_key(row) or incident.change_id,
        predicted=sorted(pred),
        observed=sorted(obs),
        hit=sorted(hit),
        missed=sorted(missed),
        overpredicted=sorted(over),
        verdict=verdict,
    )


def score_all(ledger, incidents: Iterable[Incident]) -> list:
    """Score every incident, worst first: understated predictions lead."""
    reports = [score(ledger, i) for i in incidents]
    rank = {UNDERSTATED: 0, NO_BASELINE: 1, HELD: 2, OVERSTATED: 3}
    reports.sort(key=lambda r: (rank.get(r.verdict, 9), r.recall, r.incident_id))
    return reports


def summarise(reports: list) -> dict:
    """Fleet-level recall across incidents.

    Reports the mean only over incidents that actually had a baseline. Folding
    NO_BASELINE in as a 0.0 would report a confident-looking number that mostly
    measures how well incidents were tagged, which is not what anyone asking
    "how good is the engine" wants.
    """
    scored = [r for r in reports if r.verdict != NO_BASELINE]
    n = len(scored)
    return {
        "incidents": len(reports),
        "scored": n,
        "no_baseline": len(reports) - n,
        "understated": sum(1 for r in reports if r.verdict == UNDERSTATED),
        "held": sum(1 for r in reports if r.verdict == HELD),
        "overstated": sum(1 for r in reports if r.verdict == OVERSTATED),
        "mean_recall": round(sum(r.recall for r in scored) / n, 4) if n else 0.0,
        "mean_precision": round(sum(r.precision for r in scored) / n, 4) if n else 0.0,
        "worst_verdict": (UNDERSTATED if any(r.verdict == UNDERSTATED for r in reports)
                          else (HELD if n else NO_BASELINE)),
    }


def feedback(reports: list) -> list:
    """Turn missed symbols into concrete precedent updates.

    This is the point of the module. A missed symbol is a dependency the memory
    does not have yet; returning it as an explicit, deduplicated update list is
    what turns a missed prediction into a better prediction next time.
    """
    out = {}
    for r in reports:
        for s in r.missed:
            entry = out.setdefault(s, {"symbol": s, "incidents": [], "recommend": None})
            entry["incidents"].append(r.incident_id)
    for entry in out.values():
        entry["incidents"] = sorted(set(entry["incidents"]))
        entry["recommend"] = (
            "add to precedent: no recorded decision covered this symbol before it broke"
        )
    return [out[k] for k in sorted(out)]
