"""Tests that the Keystone skill runner AUTOMATES the governed-review workflow.

Drives skills/keystone/run_review.governed_review against the real core through
injected get/post callables (no server, no extra deps), proving the skill runs
impact -> precedent -> (decision) -> chain, surfaces the contradiction, and
records a verifiable ledger row. This is the compliance proof: the artifact
performs a workflow, not a chat.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "skills", "keystone")))

import pytest
from core import fixtures, graph as graph_mod, impact as impact_mod
from core.audit import Ledger
import run_review


@pytest.fixture
def wired(tmp_path):
    """Build a temp graph + seeded ledger and return (get_json, post_json) that
    route the API paths to the real core, exactly like the backend does."""
    dpath = tmp_path / "fixture.duckdb"
    fixtures.build_fixture_duckdb(str(dpath))
    graph_mod.FIXTURE_DUCKDB = str(dpath)
    g = graph_mod.Graph(prefer_live=False)
    led = Ledger(str(tmp_path / "ledger.jsonl"))
    for row in fixtures.seed_ledger_rows():
        sig = impact_mod.blast_radius_signature(row["blast_radius_set"], row.get("epicenter_id"))
        led.append(actor=row["actor"], change_id=row["change_id"], target_symbols=row["target_symbols"],
                   blast_radius_set=row["blast_radius_set"], signature=sig,
                   decision=row["decision"], rationale=row["rationale"])

    def get_json(path):
        if path.startswith("/api/impact/"):
            name = path.rsplit("/", 1)[-1]
            imp = impact_mod.compute_blast_radius(g, name)
            return imp.to_dict() if imp else {}
        if path.startswith("/api/precedent/"):
            name = path.rsplit("/", 1)[-1]
            imp = impact_mod.compute_blast_radius(g, name)
            return led.precedent(target_symbols=[name], signature=imp.signature if imp else None)
        if path == "/api/audit/verify":
            return led.verify()
        raise AssertionError("unexpected GET " + path)

    def post_json(path, body):
        assert path == "/api/approve"
        imp = impact_mod.compute_blast_radius(g, body["name"])
        row = led.append(actor=body["reviewer"], change_id="KS-" + body["name"],
                         target_symbols=[body["name"]], blast_radius_set=imp.affected_ids,
                         signature=imp.signature, decision=body["decision"], rationale=body["rationale"])
        return {"row": row, "verify": led.verify()}

    yield get_json, post_json
    g.close()


def test_workflow_runs_and_surfaces_contradiction(wired):
    get_json, post_json = wired
    rep = run_review.governed_review("tokenize", get_json, post_json)
    assert rep["steps"] == ["impact", "precedent", "verify"]      # it ran the workflow
    assert rep["counts"]["total_affected"] == 5                    # engine number, not invented
    assert rep["precedent"]["rejected"] >= 1
    assert rep["precedent"]["contradiction"] is not None           # the load-bearing beat
    assert rep["precedent"]["contradiction_same_signature"] is True


def test_workflow_records_a_verifiable_decision(wired):
    get_json, post_json = wired
    rep = run_review.governed_review("parse", get_json, post_json,
                                     decide="approve", reviewer="vaibhav", reason="reviewed, safe")
    assert "approve" in rep["steps"]
    assert rep["recorded"]["decision"] == "approve"
    assert rep["recorded"]["actor"] == "vaibhav"
    assert rep["chain_after"]["ok"] is True                        # chain still verifies after the write


def test_decision_requires_reviewer_and_reason(wired):
    get_json, post_json = wired
    rep = run_review.governed_review("parse", get_json, post_json, decide="approve")
    assert "error" in rep                                          # gate enforces a recorded reason


def test_unknown_symbol_is_reported_not_invented(wired):
    get_json, post_json = wired
    rep = run_review.governed_review("nope_not_here", get_json, post_json)
    assert "error" in rep and "not found" in rep["error"]
