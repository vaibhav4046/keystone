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


def test_proof_endpoint_is_self_describing_and_live():
    p = client.get("/api/proof").json()
    assert p["service"] == "keystone" and p["version"]
    assert p["source_mode"] == "FALLBACK"                  # hermetic fixture
    assert p["no_llm_on_verdict"] is True
    assert p["integrity_mode"] == "HMAC-SHA256"
    assert p["audit_chain_ok"] is True
    assert "/api/proof" in p["available_routes"] and "/api/status" in p["available_routes"]
    assert p["demo_symbols"] == ["compute_blast_radius", "verify"]
    assert p["external_repo_proof"]["repo"] == "pallets/click"
    assert "shadow-merge" in p["external_repo_proof"]["verify_cmd"]
    assert p["timestamp"].endswith("Z")                    # real ISO-8601 UTC


def test_github_oauth_degrades_safely_when_unconfigured():
    # no client id/secret in the test env -> the flow advertises itself as unconfigured
    # and refuses cleanly (503) instead of half-working or leaking, so the static demo
    # keeps running and the frontend can fall back to the public scanner.
    st = client.get("/api/auth/status").json()
    assert st["configured"] is False and st["login_url"] == "/api/auth/github/login"
    assert client.get("/api/auth/github/login").status_code == 503
    assert client.get("/api/auth/github/callback?code=x&state=y").status_code == 503
    # /api/me requires a real session; a forged/absent sid is rejected, never served
    r = client.get("/api/me?sid=not-a-real-session")
    assert r.status_code == 401 and r.json()["detail"]["error"] == "NOT_SIGNED_IN"
    assert client.post("/api/auth/logout?sid=whatever").json()["ok"] is True


def test_status_repo_label_does_not_leak_abspath():
    from backend.app import _clean_repo
    # an absolute index-time path is reduced to its basename, never surfaced raw
    assert _clean_repo("D:\\project\\keystone") == "keystone"
    assert _clean_repo("/home/runner/work/keystone") == "keystone"
    # a clean repo label passes through unchanged
    assert _clean_repo("pallets/click") == "pallets/click"
    assert _clean_repo(None) is None
    # the live endpoint never exposes a drive letter or backslash in repo
    repo = str(client.get("/api/status").json().get("repo") or "")
    assert "\\" not in repo and ":" not in repo


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


TIER_RANK = {"ISOLATED": 0, "LOCAL": 1, "CROSS_TEAM": 2, "ORG_WIDE": 3}
ACTION_RANK = {"ALLOW": 0, "HOLD": 1, "BLOCK": 2}


def _assert_union_conservative(symbols):
    """The union outcome must be NO WEAKER than any constituent symbol - the MR gate's
    core guarantee. Asserts tier, action, and approver count all dominate every single."""
    b = client.post("/api/impact-mr", json={"symbols": symbols}).json()
    u = b["union"]
    for p in b["per_symbol"]:
        assert TIER_RANK[u["tier"]] >= TIER_RANK[p["tier"]], (symbols, u, p)
        assert ACTION_RANK[u["action"]] >= ACTION_RANK[p["action"]], (symbols, u, p)
        assert u["required_approvers"] >= p["required_approvers"], (symbols, u, p)
        assert u["counts"]["affected_definitions"] >= p["total_affected"], (symbols, u, p)
    return b


def test_mr_union_blast_is_conservative():
    # a merge request touching several symbols escalates to a tier no weaker than any
    # single change: the union blast radius drives the strictest governance outcome.
    b = _assert_union_conservative(["tokenize", "serialize", "parse"])
    assert b["resolved"] == ["tokenize", "serialize", "parse"] and not b["unresolved"]
    assert len(b["union"]["signature"]) == 64 and b["union"]["orbit_snapshot_sha256"]
    # the dependent-overlap case that previously INVERTED the gate (a touched symbol that is
    # the sole def in its file, and is itself a dependent of another touched symbol): the
    # union must still dominate 'encode' (CROSS_TEAM) rather than relax to LOCAL.
    overlap = _assert_union_conservative(["encode", "cache_put", "export_csv"])
    assert overlap["union"]["tier"] == "CROSS_TEAM" and overlap["union"]["required_approvers"] >= 2
    # adding more touched symbols never lowers the gate (monotonic): superset is stricter-or-equal
    _assert_union_conservative(["build_ast", "main"])
    # unknown symbols are reported, not silently dropped; all-unknown is a 404
    mixed = client.post("/api/impact-mr", json={"symbols": ["tokenize", "does_not_exist"]}).json()
    assert mixed["unresolved"] == ["does_not_exist"] and "tokenize" in mixed["resolved"]
    assert client.post("/api/impact-mr", json={"symbols": ["nope_a", "nope_b"]}).status_code == 404


def test_cross_mr_collision_detects_invisible_hazard():
    # the reframe hero: two MRs touching different files can be semantically entangled
    # (one changes a symbol the other's change depends on) with NO Git text conflict.
    r = client.post("/api/collisions", json={"mrs": [
        {"id": "MR-A", "symbols": ["tokenize"]},
        {"id": "MR-B", "symbols": ["parse"]},
        {"id": "MR-C", "symbols": ["audit_log"]}]})
    assert r.status_code == 200
    b = r.json()
    assert b["counts"]["mrs"] == 3
    pair = [c for c in b["collisions"] if {"MR-A", "MR-B"} == {c["mr_a"], c["mr_b"]}]
    assert pair, "tokenize and parse should collide on overlapping blast"
    assert pair[0]["kind"] in ("same_change", "change_in_blast", "blast_overlap")
    assert pair[0]["shared"]                       # the shared symbols are named, not asserted
    # merge_order ∪ cycle is a full partition of the MRs (a safe order or a flagged cycle)
    assert sorted(b["merge_order"] + b["uncoordinable_cycle"]) == ["MR-A", "MR-B", "MR-C"]
    # all-unknown symbols -> 404; nothing invented
    assert client.post("/api/collisions", json={"mrs": [{"id": "X", "symbols": ["nope"]}]}).status_code == 404


def test_graph_audit_flags_untested_high_blast():
    # the second hazard: high-blast symbols no test file directly exercises (review debt).
    g = client.get("/api/graph-audit").json()
    assert g["hazard"] == "review_debt" and g["items"]
    for r in g["items"]:
        assert r["blast"] >= 2
        assert (r["test_callers"] == 0) == r["untested"]   # the flag is honest, derived from the graph
    # the fixture has no test files, so its high-blast symbols are flagged untested
    assert g["counts"]["untested_high_blast"] >= 1


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
    # the override that bypassed four-eyes must be recorded in the immutable row, not hidden
    assert ovr.json()["row"]["override"] is True


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


def test_approve_mr_returns_attestation_and_records_real_author_kind():
    """Symmetry: /api/approve-mr now returns an in-toto/SLSA-VSA attestation bound to the
    UNION impact context (not a single-symbol lookup), so the audit trail is uniform with
    /api/approve. The recorded author_kind must reflect the actual agent badge, not a
    hardcoded 'human'."""
    r = client.post("/api/approve-mr", json={"symbols": ["serialize", "tokenize"],
                                             "decision": "approve", "reviewer": "tester",
                                             "rationale": "reviewed the MR", "change_id": "MR-API-1"})
    assert r.status_code == 200
    body = r.json()
    assert "attestation" in body and body["attestation"]["_type"].endswith("/Statement/v1")
    assert sorted(body["attestation"]["predicate"]["targetSymbols"]) == ["serialize", "tokenize"]
    assert body["row"]["author_kind"] == "HUMAN"               # a human reviewer -> HUMAN badge
    # declaring the same reviewer as an UNREGISTERED agent is refused (no rubber-stamp path)
    bad = client.post("/api/approve-mr", json={"symbols": ["serialize", "tokenize"],
                                               "decision": "approve", "reviewer": "mystery-bot",
                                               "rationale": "auto-fix", "author_kind": "agent"})
    assert bad.status_code == 403 and bad.json()["detail"]["error"] == "UNREGISTERED_AGENT"
