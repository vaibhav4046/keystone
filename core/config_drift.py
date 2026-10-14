"""Configuration drift: did the rules under which decisions were recorded change?

The problem this solves
-----------------------
Keystone pins the policy hash into every ledger row, and pins the Orbit snapshot
hash into every attestation. Those pins are only useful if something reads them
back. Nothing did, until now.

Concretely: an engineer edits `.keystone/policy.json` to loosen a tier, or the
graph is re-indexed and a symbol's blast radius shifts. Every decision already in
the ledger was made under the OLD configuration, but the ledger still shows them
as approvals with a green chain. Nothing is broken; the evidence has just quietly
stopped describing the rules that produced it.

This module answers the question a reviewer should be asking before trusting any
of it: *was this decision made under the policy that is in force now?*

Verdicts
--------
``CURRENT``  the row was recorded under the policy in force now
``DRIFT``    the policy has changed since the row was written
``UNKNOWN``  the row carries no pinned hash, so it cannot be checked

UNKNOWN is deliberately not CURRENT. A row we cannot check is missing evidence,
and folding it into "current" would produce a confident-looking report that is
mostly measuring which rows happen to carry a pin.

Honest limits, stated rather than hidden
----------------------------------------
Drift is not wrongdoing. A policy change may be perfectly intended, and the right
response is usually to re-review the affected decisions, not to accuse anyone.
This reports a fact about configuration history and refuses to assign intent.

It also only reads the policy hash. Whether a drifted row would actually have
decided differently is not computable from the ledger, because the ledger stores
the decision, not the policy evaluation that produced it. ``DRIFT`` means
"re-review this", not "this decision was wrong".
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from core.policy import policy_hash

CURRENT = "CURRENT"
DRIFT = "DRIFT"
UNKNOWN = "UNKNOWN"

_POLICY_KEYS = ("policy_hash",)
_ROW_VERDICTS = (CURRENT, DRIFT, UNKNOWN)


@dataclass
class RowDrift:
    """Configuration state for a single recorded decision."""
    seq: int
    change_id: str
    decision: str
    recorded_policy_hash: str
    current_policy_hash: str
    verdict: str

    @property
    def drifted(self) -> bool:
        return self.verdict == DRIFT

    def to_dict(self) -> dict:
        return {
            "seq": self.seq,
            "change_id": self.change_id,
            "decision": self.decision,
            "recorded_policy_hash": self.recorded_policy_hash,
            "current_policy_hash": self.current_policy_hash,
            "verdict": self.verdict,
        }


@dataclass
class DriftReport:
    current_policy_hash: str
    rows: list = field(default_factory=list)

    @property
    def drifted(self) -> list:
        return [r for r in self.rows if r.drifted]

    @property
    def unknown(self) -> list:
        return [r for r in self.rows if r.verdict == UNKNOWN]

    @property
    def verdict(self) -> str:
        if self.drifted:
            return DRIFT
        if self.rows and len(self.unknown) == len(self.rows):
            return UNKNOWN
        return CURRENT

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "current_policy_hash": self.current_policy_hash,
            "counts": {
                "rows": len(self.rows),
                "current": sum(1 for r in self.rows if r.verdict == CURRENT),
                "drift": len(self.drifted),
                "unknown": len(self.unknown),
            },
            "rows": [r.to_dict() for r in self.rows],
        }


def _row_policy_hash(row: dict) -> str:
    for k in _POLICY_KEYS:
        v = row.get(k)
        if v:
            return str(v)
    return ""


def audit(ledger, *, policy: Optional[dict] = None) -> DriftReport:
    """Compare every recorded row's pinned policy hash to the policy in force now."""
    current = policy_hash(policy)
    rows = []
    raw = ledger.rows() if hasattr(ledger, "rows") else []
    for i, row in enumerate(raw):
        recorded = _row_policy_hash(row)
        if not recorded:
            verdict = UNKNOWN
        elif recorded == current:
            verdict = CURRENT
        else:
            verdict = DRIFT
        rows.append(RowDrift(
            seq=int(row.get("seq", i) or i),
            change_id=str(row.get("change_id") or ""),
            decision=str(row.get("decision") or ""),
            recorded_policy_hash=recorded,
            current_policy_hash=current,
            verdict=verdict,
        ))
    return DriftReport(current_policy_hash=current, rows=rows)


def re_review_queue(report: DriftReport) -> list:
    """The decisions that need a human to look at them again.

    Drift on an APPROVE is the expensive case: an approval that was earned under
    a stricter policy is still recorded as an approval, and a later change to the
    same symbols will find that precedent and pass. Drift on a REJECT is cheaper
    (it can only be over-cautious), but it is listed too, because a policy change
    that loosened a tier may mean those symbols should be reconsidered.
    """
    out = []
    for r in report.drifted:
        out.append({
            "seq": r.seq,
            "change_id": r.change_id,
            "decision": r.decision,
            "reason": "recorded under a different policy than the one now in force",
            "risk": "high" if r.decision.upper() == "APPROVE" else "low",
            "action": "re-review under the current policy",
        })
    out.sort(key=lambda x: (0 if x["risk"] == "high" else 1, x["seq"]))
    return out


def load_ledger(path: str):
    """Open a ledger without hard-failing on a missing file."""
    from core.audit import Ledger
    return Ledger(path if os.path.exists(path) else os.devnull)
