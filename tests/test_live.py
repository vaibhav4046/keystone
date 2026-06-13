"""Live-graph invariants, gated. Skipped unless KEYSTONE_PREFER_LIVE=1 and a real
Orbit DuckDB exists at ~/.orbit/graph.duckdb. Converts the README's live claims
(a real symbol has a non-zero blast radius; an adaptive contradiction can fire)
into a tested invariant on machines that have indexed a repo. CI (no live graph)
skips this cleanly.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from core import graph as graph_mod, impact as impact_mod, seed as seed_mod
from core.audit import Ledger

_LIVE = os.environ.get("KEYSTONE_PREFER_LIVE") == "1" and os.path.exists(graph_mod.LIVE_DUCKDB)
pytestmark = pytest.mark.skipif(not _LIVE, reason="no live Orbit graph (set KEYSTONE_PREFER_LIVE=1 and index a repo)")


def test_live_top_symbol_has_blast_radius():
    g = graph_mod.Graph(prefer_live=True)
    try:
        assert g.source.mode == "LIVE"
        names = g.all_definition_names(limit=5)
        assert names, "live graph has no reviewable symbols"
        imp = impact_mod.compute_blast_radius(g, names[0])
        assert imp is not None and imp.counts["total_affected"] >= 1   # the top fan-in symbol has dependents
        assert imp.signature and imp.epicenter_fqn
    finally:
        g.close()


def test_live_adaptive_contradiction_fires(tmp_path):
    g = graph_mod.Graph(prefer_live=True)
    try:
        led = Ledger(str(tmp_path / "ledger.jsonl"))
        for row in seed_mod.seed_rows_for(g):
            sig = impact_mod.blast_radius_signature(row["blast_radius_set"], row.get("epicenter_id"))
            led.append(actor=row["actor"], change_id=row["change_id"], target_symbols=row["target_symbols"],
                       blast_radius_set=row["blast_radius_set"], signature=sig,
                       decision=row["decision"], rationale=row["rationale"])
        top = g.all_definition_names(limit=1)[0]
        imp = impact_mod.compute_blast_radius(g, top)
        prec = led.precedent(target_symbols=[top], signature=imp.signature)
        assert prec["contradiction"] is not None and prec["contradiction_same_signature"] is True
    finally:
        g.close()
