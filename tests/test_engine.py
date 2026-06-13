"""Exact-result tests for the deterministic engine, audit chain, and precedent.

These prove the spec's load-bearing claims: every number is reproducible from the
graph, the hash chain detects tampering, and precedent recall surfaces a real
contradiction. Run: python -m pytest tests/test_engine.py -q
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from core import fixtures, graph as graph_mod, impact as impact_mod
from core.audit import Ledger


@pytest.fixture(scope="module")
def graph(tmp_path_factory):
    p = tmp_path_factory.mktemp("kg") / "fixture.duckdb"
    fixtures.build_fixture_duckdb(str(p))
    # point the engine at this fixture by forcing fallback to it
    graph_mod.FIXTURE_DUCKDB = str(p)
    g = graph_mod.Graph(prefer_live=False)
    yield g
    g.close()


def test_blast_radius_exact_counts(graph):
    imp = impact_mod.compute_blast_radius(graph, "tokenize", max_depth=3)
    assert imp is not None
    assert imp.epicenter_name == "tokenize"
    assert imp.counts["ring_1"] == 1        # parse
    assert imp.counts["ring_2"] == 2        # build_ast, lint
    assert imp.counts["ring_3"] == 2        # compile_unit, format_src
    assert imp.counts["total_affected"] == 5
    assert imp.affected_ids == [2, 3, 4, 6, 7]
    assert imp.counts["unaffected"] == 4    # main, log_event, load_config, Token


def test_signature_is_stable_and_set_based(graph):
    a = impact_mod.compute_blast_radius(graph, "tokenize", max_depth=3).signature
    b = impact_mod.compute_blast_radius(graph, "tokenize", max_depth=3).signature
    assert a == b                            # deterministic
    assert a == impact_mod.blast_radius_signature([7, 4, 3, 2, 6])  # order-independent


def test_unknown_symbol_returns_none(graph):
    assert impact_mod.compute_blast_radius(graph, "does_not_exist") is None


def test_independent_recompute_matches(graph):
    """Round-two QA: recompute total_affected by a separate code path and match."""
    imp = impact_mod.compute_blast_radius(graph, "tokenize", max_depth=3)
    # independent BFS over raw edges via the connection (real Orbit edge columns)
    con = graph._con
    edges = con.execute(
        "SELECT source_id, target_id FROM gl_edge WHERE relationship_kind='CALLS' "
        "AND source_kind='Definition' AND target_kind='Definition'").fetchall()
    rev = {}
    for s, d in edges:
        rev.setdefault(d, set()).add(s)
    seen, frontier, depth = set(), {1}, 0
    while frontier and depth < 3:
        nxt = set()
        for n in frontier:
            for c in rev.get(n, ()):
                if c not in seen and c != 1:
                    seen.add(c); nxt.add(c)
        frontier = nxt; depth += 1
    assert sorted(seen) == imp.affected_ids


def test_audit_chain_appends_and_verifies(tmp_path):
    led = Ledger(str(tmp_path / "ledger.jsonl"))
    led.append(actor="a", change_id="MR-1", target_symbols=["x"], blast_radius_set=[2, 3],
               signature="sig1", decision="approve", rationale="ok")
    led.append(actor="b", change_id="MR-2", target_symbols=["y"], blast_radius_set=[4],
               signature="sig2", decision="reject", rationale="no")
    v = led.verify()
    assert v["ok"] is True and v["count"] == 2 and v["broken_index"] is None


def test_audit_chain_detects_tampering(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    led = Ledger(path)
    led.append(actor="a", change_id="MR-1", target_symbols=["x"], blast_radius_set=[2],
               signature="s", decision="approve", rationale="first")
    led.append(actor="b", change_id="MR-2", target_symbols=["y"], blast_radius_set=[3],
               signature="s", decision="approve", rationale="second")
    led.append(actor="c", change_id="MR-3", target_symbols=["z"], blast_radius_set=[4],
               signature="s", decision="reject", rationale="third")
    # tamper: rewrite row 1's rationale on disk without fixing the hash
    raw = open(path, encoding="utf-8").read().splitlines()
    raw[1] = raw[1].replace('"second"', '"SECOND-EDITED"')
    open(path, "w", encoding="utf-8").write("\n".join(raw) + "\n")
    v = led.verify()
    assert v["ok"] is False and v["broken_index"] == 1


def test_precedent_surfaces_contradiction(tmp_path):
    """Seed a prior REJECT on tokenize, then a pending approve must see the contradiction."""
    path = str(tmp_path / "ledger.jsonl")
    led = Ledger(path)
    for row in fixtures.seed_ledger_rows():
        sig = impact_mod.blast_radius_signature(row["blast_radius_set"])
        led.append(actor=row["actor"], change_id=row["change_id"],
                   target_symbols=row["target_symbols"], blast_radius_set=row["blast_radius_set"],
                   signature=sig, decision=row["decision"], rationale=row["rationale"])
    # use the SAME signature the engine computes for tokenize at default depth
    live_sig = impact_mod.blast_radius_signature([2, 3, 4, 6, 7])
    prec = led.precedent(target_symbols=["tokenize"], signature=live_sig)
    assert prec["match_count"] >= 1
    assert prec["rejected"] >= 1
    assert prec["contradiction"] is not None
    assert prec["contradiction"]["actor"] == "s.castellano"
    assert "RFC" in prec["contradiction"]["rationale"]
    # the strongest form: the prior rejection has the IDENTICAL blast signature
    assert prec["contradiction_same_signature"] is True


def test_contradiction_signature_matches_live_blast(graph):
    """End-to-end: the engine-computed signature for tokenize equals the seeded
    rejection's signature, so the signature-identical contradiction genuinely fires."""
    imp = impact_mod.compute_blast_radius(graph, "tokenize", max_depth=3)
    seed = [r for r in fixtures.seed_ledger_rows() if r["change_id"] == "MR-203"][0]
    assert impact_mod.blast_radius_signature(seed["blast_radius_set"]) == imp.signature
