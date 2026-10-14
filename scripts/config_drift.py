"""Configuration-drift report: were the recorded decisions made under today's rules?

    python scripts/config_drift.py                     # report
    python scripts/config_drift.py --json              # machine readable
    python scripts/config_drift.py --fail-on-drift     # enforce

Keystone pins the policy hash into every ledger row and never checked it back.
An edited policy left every prior approval still looking valid under rules that
had stopped existing. This reads the pins back and reports which decisions need a
human to look again.

Exits non-zero on DRIFT. Note that DRIFT is a fact about configuration history,
not an accusation: a policy change is often intended, and the correct response is
to re-review, not to blame. UNKNOWN does not fail the build either, because a row
we cannot check is missing evidence rather than a known problem.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.config_drift import (CURRENT, DRIFT, UNKNOWN, audit,  # noqa: E402
                               load_ledger, re_review_queue)


def build_report(ledger_path: str) -> dict:
    rep = audit(load_ledger(ledger_path))
    d = rep.to_dict()
    d["ok"] = True
    d["re_review_queue"] = re_review_queue(rep)
    return d


def render(rep: dict) -> str:
    c = rep.get("counts", {})
    out = [
        "Configuration drift - were decisions recorded under the policy now in force?",
        "",
        f"  current policy hash: {rep.get('current_policy_hash', '')[:16]}...",
        f"  rows={c.get('rows', 0)}  current={c.get('current', 0)}  "
        f"drift={c.get('drift', 0)}  unknown={c.get('unknown', 0)}",
        f"  verdict: {rep.get('verdict')}",
        "",
    ]
    for r in rep.get("rows", []):
        if r["verdict"] == CURRENT:
            continue
        out.append(f"[{r['verdict']}] seq={r['seq']} {r['change_id']} ({r['decision']})")
        if r["verdict"] == DRIFT:
            out.append(f"          recorded {r['recorded_policy_hash'][:16]}... "
                       f"vs current {r['current_policy_hash'][:16]}...")
        else:
            out.append("          no policy hash pinned on this row; cannot be checked")
    if rep.get("re_review_queue"):
        out.append("")
        out.append("  re-review queue (drifted approvals first):")
        for e in rep["re_review_queue"]:
            out.append(f"    [{e['risk']:>4}] {e['change_id']}: {e['action']}")
    elif rep.get("verdict") == CURRENT:
        out.append("  every checkable decision was recorded under the policy in force now.")
    out.append("")
    out.append(f"overall: {rep.get('verdict')}")
    if rep.get("verdict") == UNKNOWN:
        out.append("  (no decision carries a pinned policy hash, so nothing could be checked)")
    return "\n".join(out)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Detect policy drift in the audit ledger")
    p.add_argument("--ledger", default=os.path.join(ROOT, "data", "audit_ledger.jsonl"))
    p.add_argument("--json", action="store_true")
    p.add_argument("--fail-on-drift", action="store_true",
                   help="exit 1 when any decision was recorded under a different policy")
    a = p.parse_args(argv)

    rep = build_report(a.ledger)
    print(json.dumps(rep, indent=2) if a.json else render(rep))
    if a.fail_on_drift and rep.get("verdict") == DRIFT:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
