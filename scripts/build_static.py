"""Precompute a static data bundle so the web hero deploys with NO backend.

Runs the deterministic engine over the fixture graph for every definition and
writes web/data.json: status, definitions, per-symbol impact and precedent, and
the seeded audit ledger. The frontend tries the live API first and falls back to
this bundle when no backend is reachable (a cold-clicked public deploy), labeled
FALLBACK. The authentic live local-graph run is shown in the demo video.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import (fixtures, graph as graph_mod, impact as impact_mod,
                  policy as policy_mod, attest as attest_mod)
from core.audit import Ledger

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
WEB = os.path.join(ROOT, "web")
FIXTURE = os.path.join(DATA, "fixture_graph.duckdb")
LEDGER = os.path.join(DATA, "audit_ledger.jsonl")
ORBIT_SAMPLE = os.path.join(WEB, "orbit_sample_transcript.json")


def _orbit_transcript():
    """The committed `glab orbit local` transcript for the FALLBACK status panel,
    so a remote judge on the public deploy sees evidence the product drives Orbit's
    own CLI. build_static NEVER captures live (that would make web/data.json drift
    per machine and break the CI drift check); the transcript is refreshed only by
    the explicit scripts/capture_orbit_transcript.py. Here we just load the committed
    sample (already sanitized)."""
    if os.path.exists(ORBIT_SAMPLE):
        try:
            with open(ORBIT_SAMPLE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def main():
    # The PUBLIC sample bundle uses a fixed, non-secret HMAC key so the committed
    # web/data.json is byte-identical on every machine (CI drift check) — the sample
    # is a build-time artifact labeled "verified at build time" in the UI, not a real
    # audit trail. Real deployments use a secret per-machine key (see core/audit.py).
    os.environ["KEYSTONE_LEDGER_KEY"] = "keystone-public-sample-v1"
    import core.audit as _audit
    _audit._CACHED_KEY = None  # force re-read with the fixed sample key

    fixtures.build_fixture_duckdb(FIXTURE)
    # fresh seeded ledger
    if os.path.exists(LEDGER):
        os.remove(LEDGER)
    led = Ledger(LEDGER)
    g = graph_mod.Graph(prefer_live=False)
    pol_active = policy_mod.load_policy()
    for row in fixtures.seed_ledger_rows():
        sig = impact_mod.blast_radius_signature(row["blast_radius_set"], row.get("epicenter_id"))
        # attach the same governance context a live deployment records, so the public
        # ledger shows the enforcement fields (tier, action, policy hash, snapshot)
        extra = {"seeded": True}
        sym = (row.get("target_symbols") or [None])[0]
        imp = impact_mod.compute_blast_radius(g, sym) if sym else None
        if imp:
            d = imp.to_dict()
            pol = policy_mod.evaluate(d, {}, pol_active)
            extra.update({"tier": pol["tier"], "governance_action": pol["action"],
                          "policy_version": pol["policy_version"], "policy_hash": pol["policy_hash"],
                          "orbit_snapshot_sha256": attest_mod.orbit_snapshot_sha256(d)})
        led.append(actor=row["actor"], change_id=row["change_id"], target_symbols=row["target_symbols"],
                   blast_radius_set=row["blast_radius_set"], signature=sig,
                   decision=row["decision"], rationale=row["rationale"], extra=extra)

    names = g.all_definition_names()
    rep = g.schema_report()
    tx = _orbit_transcript()
    cli_ran = any(e.get("ok") for e in tx)
    bundle = {
        "static": True,
        "status": {
            "source_mode": "FALLBACK",
            # honest: the public deploy reads the committed fixture, but a REAL orbit
            # CLI run is recorded in the transcript below (captured on the live graph)
            "orbit_access": "CLI-recorded + DuckDB-fixture" if cli_ran else "DuckDB-fixture",
            "duckdb_path": "data/fixture_graph.duckdb (committed sample)",
            "tables": rep["tables"],
            "audit_chain": led.verify(),
            "definitions": g.total_definitions(),
            "integrity": {"hmac": True, "approve_token_required": False,
                          "reviewer_verified": False, "open_mode": True, "override_token_required": False},
            "window_enforced": bool(pol_active.get("window_enforced")),
            # a real captured `orbit schema` + `orbit sql` transcript (recorded), so the
            # public FALLBACK deploy still shows the product driving Orbit's own CLI
            "orbit_cli_transcript": tx,
            "orbit_cli_recorded": cli_ran,
        },
        "definitions": names,
        "impact": {},
        "precedent": {},
        "policy": {"policy": policy_mod.load_policy(), "policy_hash": policy_mod.policy_hash()},
        "attestation": {},
        "audit": {"rows": led.rows(), "verify": led.verify()},
    }
    rows = led.rows()
    for n in names:
        imp = impact_mod.compute_blast_radius(g, n)
        if not imp:
            continue
        d = imp.to_dict()
        prec = led.precedent(target_symbols=[n], signature=imp.signature)
        pol = policy_mod.evaluate(d, prec)
        d["policy"] = pol
        d["orbit_snapshot_sha256"] = attest_mod.orbit_snapshot_sha256(d)
        bundle["impact"][n] = d
        bundle["precedent"][n] = prec
        # precompute an attestation for any symbol that already has a seeded decision
        match = [r for r in rows if n in (r.get("target_symbols") or [])]
        if match:
            bundle["attestation"][n] = attest_mod.build_attestation(
                impact_dict=d, policy_eval=pol, row=match[0], source_mode="FALLBACK")
    g.close()

    out = os.path.join(WEB, "data.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(bundle, f, separators=(",", ":"))
    print(f"wrote {out}  ({len(names)} symbols, {os.path.getsize(out)} bytes)")


if __name__ == "__main__":
    main()
