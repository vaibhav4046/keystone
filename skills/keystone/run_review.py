"""Keystone governed-review workflow runner (the SKILL's runnable action).

This is the proof that the Keystone skill AUTOMATES a workflow rather than
chatting: given a symbol it calls the Keystone API to fetch the deterministic
blast radius and the precedent, prints a governed-review report, and optionally
records a human decision into the tamper-evident ledger, then confirms the chain.

It talks to the API through two injected callables (get_json, post_json) so the
same orchestration is testable in-process and runnable against a live server.
Standard library only for the live path (urllib).
"""
from __future__ import annotations

import argparse
import json
import sys
from urllib import request, parse


def _urllib_get(base):
    def g(path):
        with request.urlopen(base + path, timeout=8) as r:
            return json.loads(r.read().decode())
    return g


def _urllib_post(base):
    def p(path, body):
        data = json.dumps(body).encode()
        req = request.Request(base + path, data=data, headers={"content-type": "application/json"}, method="POST")
        with request.urlopen(req, timeout=8) as r:
            return json.loads(r.read().decode())
    return p


def governed_review(symbol, get_json, post_json=None, *, decide=None, reviewer=None, reason=None):
    """Run the workflow. Returns a structured report dict. Records a decision iff
    decide is given (with reviewer and reason). Never invents numbers; never
    auto-decides."""
    report = {"symbol": symbol, "steps": []}

    imp = get_json(f"/api/impact/{parse.quote(symbol)}")
    if imp is None or "counts" not in imp:
        report["error"] = f"symbol not found in graph: {symbol}"
        return report
    report["steps"].append("impact")
    report["epicenter"] = imp["epicenter"]
    report["counts"] = imp["counts"]
    report["signature"] = imp["signature"]

    prec = get_json(f"/api/precedent/{parse.quote(symbol)}")
    report["steps"].append("precedent")
    report["precedent"] = {
        "matches": prec.get("match_count", 0),
        "approved": prec.get("approved", 0),
        "rejected": prec.get("rejected", 0),
        "contradiction": prec.get("contradiction"),
        "contradiction_same_signature": prec.get("contradiction_same_signature", False),
    }

    if decide:
        if not reviewer or not reason:
            report["error"] = "a decision requires --reviewer and --reason"
            return report
        if decide not in ("approve", "reject"):
            report["error"] = "decision must be approve or reject"
            return report
        res = post_json("/api/approve", {"name": symbol, "decision": decide,
                                         "reviewer": reviewer, "rationale": reason})
        report["steps"].append("approve")
        report["recorded"] = res.get("row")
        report["chain_after"] = res.get("verify")
    else:
        report["chain"] = get_json("/api/audit/verify")
        report["steps"].append("verify")
    return report


def _print_report(rep):
    if rep.get("error"):
        print("ERROR:", rep["error"]); return
    c = rep["counts"]
    print(f"\nKEYSTONE governed review : {rep['symbol']}")
    print(f"  blast radius : ring1={c.get('ring_1',0)} ring2={c.get('ring_2',0)} "
          f"affected={c['total_affected']} unaffected={c['unaffected']}")
    print(f"  signature    : {rep['signature'][:16]}...")
    p = rep["precedent"]
    print(f"  precedent    : {p['matches']} matches  approved={p['approved']} rejected={p['rejected']}")
    if p["contradiction"]:
        cc = p["contradiction"]
        tag = "identical-signature " if p["contradiction_same_signature"] else ""
        print(f"  CONTRADICTION ({tag}): {cc['actor']} rejected {cc['change_id']} : \"{cc['rationale']}\" (row #{cc['seq']})")
    if rep.get("recorded"):
        r = rep["recorded"]
        print(f"  recorded     : {r['decision']} by {r['actor']} -> row #{r['seq']} {r['row_hash'][:12]}...")
        print(f"  chain        : {'VERIFIED' if rep['chain_after']['ok'] else 'BROKEN@' + str(rep['chain_after']['broken_index'])}")
    elif rep.get("chain"):
        print(f"  chain        : {'VERIFIED' if rep['chain']['ok'] else 'BROKEN@' + str(rep['chain']['broken_index'])}")
    print()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Keystone governed-review workflow")
    ap.add_argument("symbol")
    ap.add_argument("--base", default="http://127.0.0.1:8787")
    ap.add_argument("--decide", choices=["approve", "reject"])
    ap.add_argument("--reviewer")
    ap.add_argument("--reason")
    a = ap.parse_args(argv)
    rep = governed_review(a.symbol, _urllib_get(a.base), _urllib_post(a.base),
                          decide=a.decide, reviewer=a.reviewer, reason=a.reason)
    _print_report(rep)
    return 0 if not rep.get("error") else 1


if __name__ == "__main__":
    sys.exit(main())
