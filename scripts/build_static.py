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

from core import fixtures, graph as graph_mod, impact as impact_mod
from core.audit import Ledger

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
WEB = os.path.join(ROOT, "web")
FIXTURE = os.path.join(DATA, "fixture_graph.duckdb")
LEDGER = os.path.join(DATA, "audit_ledger.jsonl")


def main():
    fixtures.build_fixture_duckdb(FIXTURE)
    # fresh seeded ledger
    if os.path.exists(LEDGER):
        os.remove(LEDGER)
    led = Ledger(LEDGER)
    for row in fixtures.seed_ledger_rows():
        sig = impact_mod.blast_radius_signature(row["blast_radius_set"])
        led.append(actor=row["actor"], change_id=row["change_id"], target_symbols=row["target_symbols"],
                   blast_radius_set=row["blast_radius_set"], signature=sig,
                   decision=row["decision"], rationale=row["rationale"])

    g = graph_mod.Graph(prefer_live=False)
    names = g.all_definition_names()
    rep = g.schema_report()
    bundle = {
        "static": True,
        "status": {
            "source_mode": "FALLBACK",
            "orbit_access": "DuckDB-fixture",
            "duckdb_path": "data/fixture_graph.duckdb (committed sample)",
            "tables": rep["tables"],
            "audit_chain": led.verify(),
            "definitions": g.total_definitions(),
            "llm_providers_configured": [],
        },
        "definitions": names,
        "impact": {},
        "precedent": {},
        "audit": {"rows": led.rows(), "verify": led.verify()},
    }
    for n in names:
        imp = impact_mod.compute_blast_radius(g, n)
        if imp:
            bundle["impact"][n] = imp.to_dict()
            bundle["precedent"][n] = led.precedent(target_symbols=[n], signature=imp.signature)
    g.close()

    out = os.path.join(WEB, "data.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(bundle, f, separators=(",", ":"))
    print(f"wrote {out}  ({len(names)} symbols, {os.path.getsize(out)} bytes)")


if __name__ == "__main__":
    main()
