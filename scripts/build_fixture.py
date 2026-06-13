"""Build the committed fixture DuckDB and seed the demo audit ledger.

Run from the project root: python scripts/build_fixture.py
Produces data/fixture_graph.duckdb and data/audit_ledger.jsonl (seeded with the
prior decisions that make the Precedent Panel surface a real contradiction).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import fixtures, graph as graph_mod, impact as impact_mod
from core.audit import Ledger

DATA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
FIXTURE = os.path.join(DATA, "fixture_graph.duckdb")
LEDGER = os.path.join(DATA, "audit_ledger.jsonl")


def main():
    os.makedirs(DATA, exist_ok=True)
    fixtures.build_fixture_duckdb(FIXTURE)
    print(f"built fixture graph: {FIXTURE}")

    # seed ledger: compute each prior decision's signature from its own affected set
    if os.path.exists(LEDGER):
        os.remove(LEDGER)
    led = Ledger(LEDGER)
    for row in fixtures.seed_ledger_rows():
        sig = impact_mod.blast_radius_signature(row["blast_radius_set"])
        led.append(actor=row["actor"], change_id=row["change_id"],
                   target_symbols=row["target_symbols"], blast_radius_set=row["blast_radius_set"],
                   signature=sig, decision=row["decision"], rationale=row["rationale"])
    v = led.verify()
    print(f"seeded ledger: {LEDGER}  rows={v['count']}  chain_ok={v['ok']}")

    # sanity: live blast radius for the demo target
    g = graph_mod.Graph(prefer_live=False)
    imp = impact_mod.compute_blast_radius(g, "tokenize")
    print(f"tokenize blast radius: counts={imp.counts}  signature={imp.signature[:12]}...")
    g.close()


if __name__ == "__main__":
    main()
