"""HTTP-layer integration tests for the FastAPI app via TestClient (no server).

Forces the committed fixture and a temp ledger through env vars set BEFORE importing
the app, so the suite is hermetic. Exercises status, definitions, impact, precedent,
the approval flow, and the validation guards (depth cap, decision enum, required
fields, max_length) that a green unit-test badge would otherwise leave unproven.
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# hermetic: fixture graph + throwaway ledger, set before importing the app
os.environ["KEYSTONE_PREFER_LIVE"] = "0"
os.environ["KEYSTONE_LLM_DISABLED"] = "1"        # no network in tests; brief falls back to deterministic
os.environ["KEYSTONE_LEDGER_PATH"] = os.path.join(tempfile.mkdtemp(), "api_ledger.jsonl")

import pytest
from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_status_is_fixture_and_hmac():
    s = client.get("/api/status").json()
    assert s["source_mode"] == "FALLBACK"
    assert s["integrity"]["hmac"] is True
    assert s["audit_chain"]["ok"] is True


def test_definitions_and_impact():
    names = client.get("/api/definitions").json()["names"]
    assert "tokenize" in names
    imp = client.get("/api/impact/tokenize").json()
    assert imp["counts"]["total_affected"] == 5
    assert imp["epicenter"]["fqn"]              # fqn surfaced for disambiguation
    assert client.get("/api/impact/does_not_exist").status_code == 404


def test_depth_cap_and_decision_validation():
    assert client.get("/api/impact/tokenize?max_depth=9999").status_code == 422   # capped 1..8
    assert client.post("/api/approve", json={"name": "tokenize", "decision": "maybe",
                                             "reviewer": "x", "rationale": "y"}).status_code == 422
    assert client.post("/api/approve", json={"name": "tokenize", "decision": "approve",
                                             "reviewer": "x", "rationale": ""}).status_code == 422


def test_review_brief_is_deterministic_without_llm():
    b = client.get("/api/brief/tokenize").json()
    assert b["deterministic"] is True and b["provider"] is None    # no LLM in tests -> deterministic
    assert "tokenize" in b["brief"] and len(b["brief"]) > 20       # a real, useful brief
    # the brief must never assert a verdict; it is advisory prose over engine facts
    assert "providers_configured" in b


def test_assistant_is_deterministic_tool_loop_without_llm():
    # no LLM in tests -> the agent runs the deterministic tool plan: a real, ordered
    # trace of engine tool calls (blast_radius -> precedent -> propose_reviewers) plus
    # a recommendation. It must NOT claim to be a live model run, and must stay advisory.
    r = client.post("/api/assistant", json={"symbol": "tokenize"})
    assert r.status_code == 200
    b = r.json()
    assert b["deterministic"] is True and b["provider"] is None
    tools = [s["tool"] for s in b["steps"]]
    assert tools == ["blast_radius", "precedent", "propose_reviewers"]   # a real tool trace
    # the trace is grounded in engine facts, not invented
    assert b["steps"][0]["result"]["tier"] == "LOCAL"
    assert "tokenize" in b["answer"] and "next step" in b["answer"].lower()
    # the agent proposes; it never records a decision (the ledger is unchanged)
    assert client.post("/api/assistant", json={"symbol": "does_not_exist"}).status_code == 404


def test_precedent_contradiction_over_http():
    p = client.get("/api/precedent/tokenize").json()
    assert p["rejected"] >= 1
    assert p["contradiction_strength"] == "identical"


def test_governance_block_refuses_approve_without_override():
    # tokenize carries a seeded identical-signature rejection -> policy action BLOCK
    r = client.post("/api/approve", json={"name": "tokenize", "decision": "approve",
                                          "reviewer": "x", "rationale": "ship it anyway"})
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "GOVERNANCE_BLOCK"
    ovr = client.post("/api/approve", json={"name": "tokenize", "decision": "approve", "reviewer": "x",
                                            "rationale": "accept risk, RFC filed", "override": True})
    assert ovr.status_code == 200 and ovr.json()["row"]["override"] is True


def test_quorum_requires_distinct_approvers():
    # serialize is CROSS_TEAM (>=2 approvers required). Seed-agnostic: a distinct
    # approver advances the quorum, the same approver twice does not.
    a = client.post("/api/approve", json={"name": "serialize", "decision": "approve",
                                          "reviewer": "qa_alice", "rationale": "looks safe"}).json()
    assert a["quorum"]["required"] >= 2
    base = a["quorum"]["confirmed"]
    same = client.post("/api/approve", json={"name": "serialize", "decision": "approve",
                                             "reviewer": "qa_alice", "rationale": "still safe"}).json()
    assert same["quorum"]["confirmed"] == base                   # same actor does not advance quorum
    diff = client.post("/api/approve", json={"name": "serialize", "decision": "approve",
                                             "reviewer": "qa_bob", "rationale": "second reviewer ok"}).json()
    assert diff["quorum"]["confirmed"] == base + 1               # a distinct actor advances it


def test_self_approval_is_blocked():
    # the author of a change cannot approve their own change (four-eyes)
    r = client.post("/api/approve", json={"name": "metrics", "decision": "approve", "reviewer": "alice",
                                          "change_author": "alice", "rationale": "lgtm"})
    assert r.status_code == 403 and r.json()["detail"]["error"] == "SELF_APPROVAL"
    ovr = client.post("/api/approve", json={"name": "metrics", "decision": "approve", "reviewer": "alice",
                                            "change_author": "alice", "rationale": "solo, accepted", "override": True})
    assert ovr.status_code == 200


def test_change_id_separates_quorum_buckets():
    # two unrelated MRs on the same symbol do NOT share a quorum pool
    a = client.post("/api/approve", json={"name": "serialize", "decision": "approve", "reviewer": "r1",
                                          "change_id": "MR-100", "rationale": "mr100"}).json()
    b = client.post("/api/approve", json={"name": "serialize", "decision": "approve", "reviewer": "r1",
                                          "change_id": "MR-200", "rationale": "mr200"}).json()
    assert a["quorum"]["confirmed"] == 1 and b["quorum"]["confirmed"] == 1   # separate buckets
    close = client.post("/api/approve", json={"name": "serialize", "decision": "approve", "reviewer": "r2",
                                              "change_id": "MR-100", "rationale": "second on mr100"}).json()
    assert close["quorum"]["status"] == "APPROVED" and close["quorum"]["confirmed"] == 2


def test_unregistered_agent_cannot_self_approve():
    r = client.post("/api/approve", json={"name": "serialize", "decision": "approve",
                                          "reviewer": "mystery-bot", "rationale": "auto-fix",
                                          "author_kind": "agent"})
    assert r.status_code == 403 and r.json()["detail"]["error"] == "UNREGISTERED_AGENT"


def test_approve_records_and_chain_verifies():
    before = client.get("/api/audit").json()["verify"]["count"]
    r = client.post("/api/approve", json={"name": "parse", "decision": "approve",
                                          "reviewer": "tester", "rationale": "reviewed, safe"})
    assert r.status_code == 200
    body = r.json()
    assert body["row"]["actor"] == "tester" and body["verify"]["ok"] is True
    assert "T" in body["row"]["ts"] and body["row"]["ts"].endswith("Z")   # real ISO timestamp
    after = client.get("/api/audit").json()["verify"]["count"]
    assert after == before + 1
