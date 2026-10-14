"""Incident-recall report: score the engine's own predictions against reality.

    python scripts/incident_recall.py                    # report from committed data
    python scripts/incident_recall.py --json             # machine readable
    python scripts/incident_recall.py --fail-on-understated

Exits non-zero when any prediction was UNDERSTATED (something broke that no
recorded decision had predicted), so it can gate a release. That direction is
deliberate: over-warning is a cost, under-warning is a defect, and a gate that
treats them equally will eventually be tuned to ignore itself.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.audit import Ledger                    # noqa: E402
from core.incident import (UNDERSTATED, Incident, feedback, score_all, summarise)  # noqa: E402

DEFAULT_LEDGER = os.path.join(ROOT, "data", "recall_fixture_ledger.jsonl")
DEFAULT_INCIDENTS = os.path.join(ROOT, "data", "incidents.example.json")
# The live ledger (data/audit_ledger.jsonl) is runtime state and is deliberately
# not tracked, so it does not exist on a clean checkout. The default is therefore a
# committed fixture: without it the example would silently score every incident as
# NO_BASELINE on a fresh clone while looking correct on a developer machine, which
# is the worst possible failure for a reproducibility claim.


def load_incidents(path: str) -> list:
    if not path or not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        rows = json.load(fh)
    rows = rows.get("incidents", []) if isinstance(rows, dict) else rows
    return [Incident(id=str(r.get("id") or f"INC-{i}"),
                     observed=list(r.get("observed") or []),
                     change_id=str(r.get("change_id") or ""),
                     summary=str(r.get("summary") or ""))
            for i, r in enumerate(rows)]


def build_report(ledger_path: str, incidents_path: str) -> dict:
    incs = load_incidents(incidents_path)
    if not incs:
        return {"ok": False, "error": "no_incidents", "incidents_path": incidents_path}
    led = Ledger(ledger_path) if os.path.exists(ledger_path) else Ledger(os.devnull)
    scored = score_all(led, incs)
    return {
        "ok": True,
        "summary": summarise(scored),
        "feedback": feedback(scored),
        "reports": [r.to_dict() for r in scored],
    }


def render(rep: dict) -> str:
    if not rep.get("ok"):
        return f"incident-recall: {rep.get('error')}\n"
    s = rep["summary"]
    out = [
        "Incident recall - were the recorded predictions right?",
        "",
        f"  incidents={s['incidents']}  scored={s['scored']}  no_baseline={s['no_baseline']}",
        f"  understated={s['understated']}  held={s['held']}  overstated={s['overstated']}",
        f"  mean recall={s['mean_recall']}  mean precision={s['mean_precision']}",
        f"  worst verdict: {s['worst_verdict']}",
        "",
    ]
    for r in rep["reports"]:
        c = r["counts"]
        out.append(f"[{r['verdict']}] {r['incident_id']}  (change {r['change_id'] or '-'})")
        out.append(f"    predicted={c['predicted']} observed={c['observed']} "
                   f"hit={c['hit']} missed={c['missed']} overpredicted={c['overpredicted']}")
        out.append(f"    precision={r['precision']} recall={r['recall']} f1={r['f1']}")
    if rep["feedback"]:
        out.append("")
        out.append("  precedent updates earned by these incidents:")
        for f in rep["feedback"]:
            out.append(f"    + {f['symbol']}  (from {', '.join(f['incidents'])})")
    out.append("")
    out.append(f"overall: {s['worst_verdict']}")
    return "\n".join(out)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Score recorded blast-radius predictions against real incidents")
    p.add_argument("--ledger", default=DEFAULT_LEDGER)
    p.add_argument("--incidents", default=DEFAULT_INCIDENTS)
    p.add_argument("--json", action="store_true")
    p.add_argument("--fail-on-understated", action="store_true",
                   help="exit 1 when any prediction was UNDERSTATED")
    a = p.parse_args(argv)

    rep = build_report(a.ledger, a.incidents)
    print(json.dumps(rep, indent=2) if a.json else render(rep))
    if a.fail_on_understated and rep.get("ok") and \
            rep["summary"]["worst_verdict"] == UNDERSTATED:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
