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
        "contradiction_strength": prec.get("contradiction_strength"),
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


def _local_callables():
    """Wire get/post directly to the in-process core (no server), so the gate runs
    in CI with nothing to start. Used by --local."""
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.abspath(os.path.join(here, "..", "..")))
    from core import graph as graph_mod, impact as impact_mod, seed as seed_mod
    from core.audit import Ledger
    g = graph_mod.Graph(prefer_live=True)
    led = Ledger(os.path.join(os.path.expanduser("~"), ".keystone", "gate_ledger.jsonl"))
    if not led.rows():
        for row in seed_mod.seed_rows_for(g):
            sig = impact_mod.blast_radius_signature(row["blast_radius_set"], row.get("epicenter_id"))
            led.append(actor=row["actor"], change_id=row["change_id"], target_symbols=row["target_symbols"],
                       blast_radius_set=row["blast_radius_set"], signature=sig,
                       decision=row["decision"], rationale=row["rationale"])

    def get_json(path):
        if path.startswith("/api/impact/"):
            imp = impact_mod.compute_blast_radius(g, parse.unquote(path.rsplit("/", 1)[-1]))
            return imp.to_dict() if imp else {}
        if path.startswith("/api/precedent/"):
            name = parse.unquote(path.rsplit("/", 1)[-1])
            imp = impact_mod.compute_blast_radius(g, name)
            return led.precedent(target_symbols=[name], signature=imp.signature if imp else None)
        if path == "/api/audit/verify":
            return led.verify()
        raise AssertionError("unexpected GET " + path)

    def post_json(path, body):
        imp = impact_mod.compute_blast_radius(g, body["name"])
        row = led.append(actor=body["reviewer"], change_id="KS-" + body["name"], target_symbols=[body["name"]],
                         blast_radius_set=imp.affected_ids, signature=imp.signature,
                         decision=body["decision"], rationale=body["rationale"])
        return {"row": row, "verify": led.verify()}

    return get_json, post_json


def main(argv=None):
    ap = argparse.ArgumentParser(description="Keystone governed-review workflow")
    ap.add_argument("symbol")
    ap.add_argument("--base", default="http://127.0.0.1:8787")
    ap.add_argument("--local", action="store_true",
                    help="run against the in-process core, no server (for CI gating)")
    ap.add_argument("--decide", choices=["approve", "reject"])
    ap.add_argument("--reviewer")
    ap.add_argument("--reason")
    ap.add_argument("--fail-on-contradiction", action="store_true",
                    help="exit non-zero when a prior identical-signature rejection exists (enforceable gate)")
    a = ap.parse_args(argv)
    get_json, post_json = _local_callables() if a.local else (_urllib_get(a.base), _urllib_post(a.base))
    rep = governed_review(a.symbol, get_json, post_json,
                          decide=a.decide, reviewer=a.reviewer, reason=a.reason)
    _print_report(rep)
    if rep.get("error"):
        return 1
    if a.fail_on_contradiction and rep.get("precedent", {}).get("contradiction_same_signature"):
        print(f"GATE BLOCKED: {a.symbol} has a prior identical-blast-radius rejection. "
              f"Resolve the precedent (RFC / explicit override) before merging.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
