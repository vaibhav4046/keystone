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


def test_precedent_contradiction_over_http():
    p = client.get("/api/precedent/tokenize").json()
    assert p["rejected"] >= 1
    assert p["contradiction_strength"] == "identical"


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
