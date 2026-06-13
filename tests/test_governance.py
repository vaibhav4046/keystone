"""Tests for the deterministic governance layer: policy tier gate, decision
attestations (in-toto / SLSA-VSA shape), and agent-scope enforcement. All pure
functions over the fixture graph; no server, no model.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from core import fixtures, graph as graph_mod, impact as impact_mod, policy as policy_mod
from core import attest as attest_mod, agents as agents_mod
from core.audit import Ledger


@pytest.fixture(scope="module")
def graph(tmp_path_factory):
    p = tmp_path_factory.mktemp("kg") / "fixture.duckdb"
    fixtures.build_fixture_duckdb(str(p))
    graph_mod.FIXTURE_DUCKDB = str(p)
    g = graph_mod.Graph(prefer_live=False)
    yield g
    g.close()


def test_policy_tier_scales_with_blast(graph):
    # tokenize: 5 affected defs across a few files -> not ISOLATED, deterministic tier
    tok = policy_mod.evaluate(impact_mod.compute_blast_radius(graph, "tokenize").to_dict(), {})
    ser = policy_mod.evaluate(impact_mod.compute_blast_radius(graph, "serialize").to_dict(), {})
    leaf = policy_mod.evaluate(impact_mod.compute_blast_radius(graph, "to_yaml").to_dict(), {})
    assert leaf["tier"] == "ISOLATED" and leaf["action"] == "ALLOW"        # no dependents
    assert ser["counts"]["affected_definitions"] == 9                       # the hub
    assert ser["required_approvers"] >= tok["required_approvers"]          # bigger blast => stricter
    assert ser["action"] in ("ALLOW", "HOLD")


def test_policy_blocks_on_identical_contradiction(graph):
    out = impact_mod.compute_blast_radius(graph, "tokenize").to_dict()
    prec = {"contradiction_strength": "identical",
            "contradiction": {"change_id": "MR-203", "actor": "s.castellano"}}
    pol = policy_mod.evaluate(out, prec)
    assert pol["action"] == "BLOCK"
    assert any("rejected before" in r for r in pol["reasons"])


def test_policy_hash_is_stable():
    assert policy_mod.policy_hash() == policy_mod.policy_hash()
    assert len(policy_mod.policy_hash()) == 64


def test_attestation_shape_and_snapshot_binding(graph, tmp_path):
    led = Ledger(str(tmp_path / "l.jsonl"))
    out = impact_mod.compute_blast_radius(graph, "tokenize").to_dict()
    pol = policy_mod.evaluate(out, {})
    snap = attest_mod.orbit_snapshot_sha256(out)
    assert snap == attest_mod.orbit_snapshot_sha256(out)                    # deterministic
    row = led.append(actor="vaibhav", change_id="KS-tokenize", target_symbols=["tokenize"],
                     blast_radius_set=[2, 3, 4, 6, 7], signature=out["signature"],
                     decision="approve", rationale="reviewed")
    att = attest_mod.build_attestation(impact_dict=out, policy_eval=pol, row=row, source_mode="FALLBACK")
    assert att["predicateType"] == "https://slsa.dev/verification_summary/v1"
    assert att["subject"][0]["digest"]["sha256"] == snap                   # bound to the graph snapshot
    assert att["predicate"]["integrity"]["sigstore"] is False              # honest: not signed
    assert att["predicate"]["tier"] == pol["tier"]
    v = attest_mod.verify_attestation(att, led)
    assert v["ok"] is True and v["row_present"] is True


def test_attestation_rejects_absent_row(graph, tmp_path):
    led = Ledger(str(tmp_path / "l.jsonl"))
    out = impact_mod.compute_blast_radius(graph, "tokenize").to_dict()
    att = attest_mod.build_attestation(impact_dict=out, policy_eval=policy_mod.evaluate(out, {}),
                                       row={"decision": "approve", "row_hash": "deadbeef", "ts": "t"},
                                       source_mode="FALLBACK")
    v = attest_mod.verify_attestation(att, led)
    assert v["ok"] is False and v["row_present"] is False


def test_agent_scope_enforced(graph):
    reg = {"agents": {"bot": {"model": "m", "allowed_paths": ["/src/parser/**"],
                              "forbidden_paths": ["/src/cli/**"], "max_blast_radius": 3}}}
    human = agents_mod.resolve_author("alice", registry=reg)
    assert human["badge"] == "HUMAN" and human["scope"] is None
    unreg = agents_mod.resolve_author("mystery", declared_kind="agent", registry=reg)
    assert unreg["badge"] == "AGENT_UNREGISTERED"
    bot = agents_mod.resolve_author("bot", declared_kind="agent", registry=reg)
    assert bot["badge"] == "AGENT_VERIFIED"
    # load_config lives in /src/cli/config.py -> forbidden for bot
    bad = agents_mod.check_scope(bot, impact_mod.compute_blast_radius(graph, "load_config").to_dict())
    assert bad["in_scope"] is False and bad["violations"]
    # tokenize lives in /src/parser/lexer.py (allowed) but blast 5 > max 3 -> still a violation
    tok = agents_mod.check_scope(bot, impact_mod.compute_blast_radius(graph, "tokenize").to_dict())
    assert tok["in_scope"] is False and any("blast radius" in v for v in tok["violations"])
