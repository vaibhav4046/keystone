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
    # unaffected = everything else in the graph (relative, so the fixture can grow)
    assert imp.counts["unaffected"] == graph.total_definitions() - 1 - imp.counts["total_affected"]


def test_serialize_hub_blast(graph):
    """The second fixture cluster: serialize is a high-fan-in hub so exploring the
    public graph beyond the tokenize demo shows real depth."""
    imp = impact_mod.compute_blast_radius(graph, "serialize", max_depth=3)
    assert imp is not None
    assert imp.counts["ring_1"] == 5                 # to_json, to_yaml, cache_put, render, export_csv
    assert imp.counts["total_affected"] == 9         # + save_doc, handle_get (r2) + handle_post, route (r3)
    # the SVG can draw real edges: every affected node has a real BFS parent
    assert all(i in imp.parents for i in imp.affected_ids)
    assert all(str(i) in imp.to_dict()["parents"] for i in imp.affected_ids)  # stringified for JSON


def test_signature_is_stable_and_set_based(graph):
    a = impact_mod.compute_blast_radius(graph, "tokenize", max_depth=3).signature
    b = impact_mod.compute_blast_radius(graph, "tokenize", max_depth=3).signature
    assert a == b                            # deterministic
    assert a == impact_mod.blast_radius_signature([7, 4, 3, 2, 6], epicenter_id=1)  # order-independent, epicenter-bound


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
        sig = impact_mod.blast_radius_signature(row["blast_radius_set"], row.get("epicenter_id"))
        led.append(actor=row["actor"], change_id=row["change_id"],
                   target_symbols=row["target_symbols"], blast_radius_set=row["blast_radius_set"],
                   signature=sig, decision=row["decision"], rationale=row["rationale"])
    # use the SAME signature the engine computes for tokenize (epicenter id 1) at default depth
    live_sig = impact_mod.blast_radius_signature([2, 3, 4, 6, 7], epicenter_id=1)
    prec = led.precedent(target_symbols=["tokenize"], signature=live_sig)
    assert prec["match_count"] >= 1
    assert prec["rejected"] >= 1
    assert prec["contradiction"] is not None
    assert prec["contradiction"]["actor"] == "s.castellano"
    assert "RFC" in prec["contradiction"]["rationale"]
    # the strongest form: the prior rejection has the IDENTICAL blast signature
    assert prec["contradiction_same_signature"] is True


def test_signature_distinguishes_symbols_with_no_dependents():
    """Two different symbols that both have an empty affected set must NOT collide
    (the old sha256(json([])) collision caused phantom contradictions)."""
    a = impact_mod.blast_radius_signature([], epicenter_id=8)
    b = impact_mod.blast_radius_signature([], epicenter_id=9)
    assert a != b


def test_forged_append_with_public_sha256_is_rejected(tmp_path):
    """An attacker who can append but lacks the HMAC key cannot forge a valid tail:
    a row whose row_hash is a plain sha256 (the public guess) fails verification."""
    import hashlib, json
    path = str(tmp_path / "ledger.jsonl")
    led = Ledger(path)
    led.append(actor="a", change_id="MR-1", target_symbols=["x"], blast_radius_set=[2],
               signature="s", decision="approve", rationale="legit")
    prev = led._read_raw()[-1]["row_hash"]
    payload = {"seq": 1, "ts": "2026-06-12T00:00:00Z", "actor": "mallory", "change_id": "MR-FORGE",
               "target_symbols": ["x"], "blast_radius_set": [2], "signature": "s",
               "decision": "approve", "rationale": "forged", "prev_hash": prev}
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    payload["row_hash"] = hashlib.sha256((prev + canon).encode()).hexdigest()  # public guess, no key
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
    v = led.verify()
    assert v["ok"] is False and v["broken_index"] == 1


def test_contradiction_strength_identical_vs_symbol(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    led = Ledger(path)
    sig = impact_mod.blast_radius_signature([2, 3], epicenter_id=1)
    led.append(actor="r", change_id="MR-9", target_symbols=["foo"], blast_radius_set=[2, 3],
               signature=sig, decision="reject", rationale="no")
    same = led.precedent(target_symbols=["foo"], signature=sig)
    assert same["contradiction_strength"] == "identical"
    diff_sig = impact_mod.blast_radius_signature([2, 3, 9], epicenter_id=1)
    diff = led.precedent(target_symbols=["foo"], signature=diff_sig)
    assert diff["contradiction_strength"] == "symbol"   # same symbol, different blast -> weaker


def test_identical_rejection_not_masked_by_later_different_signature(tmp_path):
    """A stale later rejection of the same symbol with a DIFFERENT blast signature must not
    mask an earlier IDENTICAL-signature rejection. The identical-signature rejection is the
    BLOCK-forcing beat, so a different-radius rejection arriving afterwards cannot quietly
    downgrade the contradiction to a weak advisory."""
    led = Ledger(str(tmp_path / "ledger.jsonl"))
    sig = impact_mod.blast_radius_signature([2, 3], epicenter_id=1)
    other = impact_mod.blast_radius_signature([2, 3, 9], epicenter_id=1)
    led.append(actor="r1", change_id="MR-1", target_symbols=["foo"], blast_radius_set=[2, 3],
               signature=sig, decision="reject", rationale="identical-radius reject")
    led.append(actor="r2", change_id="MR-2", target_symbols=["foo"], blast_radius_set=[2, 3, 9],
               signature=other, decision="reject", rationale="different-radius reject")
    prec = led.precedent(target_symbols=["foo"], signature=sig)
    assert prec["contradiction_same_signature"] is True
    assert prec["contradiction_strength"] == "identical"        # not downgraded by the later reject
    assert prec["contradiction"]["rationale"] == "identical-radius reject"


def test_precedent_suppresses_cross_namespace_collision(tmp_path):
    """A prior reject on mod_a.parse must NOT contradict a review of mod_b.parse
    (same short name, different fqn) - fqn is authoritative when both sides have one."""
    led = Ledger(str(tmp_path / "ledger.jsonl"))
    led.append(actor="r", change_id="MR-A", target_symbols=["parse"], target_fqns=["mod_a.parse"],
               blast_radius_set=[2, 3], signature="sigA", decision="reject", rationale="no")
    same_ns = led.precedent(target_symbols=["parse"], target_fqns=["mod_a.parse"])
    assert same_ns["contradiction"] is not None and same_ns["contradiction_matched_by"] == "fqn"
    other_ns = led.precedent(target_symbols=["parse"], target_fqns=["mod_b.parse"])
    assert other_ns["contradiction"] is None and other_ns["match_count"] == 0   # no phantom contradiction


def test_contradiction_signature_matches_live_blast(graph):
    """End-to-end: the engine-computed signature for tokenize equals the seeded
    rejection's signature, so the signature-identical contradiction genuinely fires."""
    imp = impact_mod.compute_blast_radius(graph, "tokenize", max_depth=3)
    seed = [r for r in fixtures.seed_ledger_rows() if r["change_id"] == "MR-203"][0]
    assert impact_mod.blast_radius_signature(seed["blast_radius_set"], seed.get("epicenter_id")) == imp.signature


def test_concurrent_appends_keep_the_chain_intact(tmp_path):
    """N threads append concurrently; the process append-lock must serialise the
    read-prev-hash-then-write so the chain stays verifiable and every row lands (no two writers
    share a prev_hash, no lost write). The single-process lock is what this proves; a multi-host
    deployment still needs an external mutex, as the README states."""
    import threading
    led = Ledger(str(tmp_path / "ledger.jsonl"))
    n = 24
    barrier = threading.Barrier(n)

    def one(i):
        barrier.wait()                                   # release all writers at once to force contention
        led.append(actor=f"r{i}", change_id=f"MR-{i}", target_symbols=["x"], blast_radius_set=[i + 2],
                   signature=f"sig{i}", decision="approve", rationale="concurrent")

    threads = [threading.Thread(target=one, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    v = led.verify()
    assert v["ok"] is True and v["count"] == n           # chain intact and every append landed
