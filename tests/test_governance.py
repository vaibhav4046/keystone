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
    org = policy_mod.evaluate(impact_mod.compute_blast_radius(graph, "audit_log").to_dict(), {})
    assert leaf["tier"] == "ISOLATED" and leaf["action"] == "ALLOW"        # no dependents
    assert ser["counts"]["affected_definitions"] == 9                       # the cross-team hub
    assert ser["required_approvers"] >= tok["required_approvers"]          # bigger blast => stricter
    assert org["tier"] == "ORG_WIDE" and org["action"] == "HOLD"           # the org-wide hub holds
    assert org["required_approvers"] == 3


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


def test_agent_scope_matches_relative_paths():
    """A real Orbit graph stores relative paths (src/...) while the manifest may use
    /src/**; the forbidden rule must still fire (the bug was a silent in_scope=True)."""
    reg = {"agents": {"bot": {"allowed_paths": ["src/parser/**"], "forbidden_paths": ["src/cli/**"],
                              "max_blast_radius": 99}}}
    bot = agents_mod.resolve_author("bot", declared_kind="agent", registry=reg)
    imp = {"owners": [{"ring": 0, "file": "src/cli/config.py"}], "counts": {"total_affected": 0}}
    assert agents_mod.check_scope(bot, imp)["in_scope"] is False
    ok = {"owners": [{"ring": 0, "file": "src/parser/lexer.py"}], "counts": {"total_affected": 0}}
    assert agents_mod.check_scope(bot, ok)["in_scope"] is True


def test_review_window_blocks_fast_close(graph, tmp_path):
    """With window_enforced, a CROSS_TEAM change cannot be closed by the second
    approver before the window elapses; the open-time is read from the ledger."""
    import datetime
    from core import gate as gate_mod
    led = Ledger(str(tmp_path / "l.jsonl"))
    pol = dict(policy_mod.DEFAULT_POLICY); pol["window_enforced"] = True
    imp = impact_mod.compute_blast_radius(graph, "serialize")
    sig = imp.signature
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    led.append(actor="a", change_id="MR-X", target_symbols=["serialize"], blast_radius_set=imp.affected_ids,
               signature=sig, decision="approve", rationale="first", ts=now)
    res = gate_mod.evaluate(graph, led, name="serialize", decision="approve", reviewer="b",
                            change_id="MR-X", policy=pol)
    assert res["ok"] is False and res["error"] == "REVIEW_WINDOW_PENDING"


def test_public_sample_key_is_forgeable(monkeypatch):
    """Honest documentation: the PUBLIC static bundle uses a published HMAC key, so
    its chain is illustrative only — anyone holding the published key reproduces a
    valid row hash. This is why the public UI labels it SAMPLE / PUBLIC KEY and the
    real per-machine key is secret."""
    import hashlib
    import hmac as _hmac
    from core import audit as A
    monkeypatch.setenv("KEYSTONE_LEDGER_KEY", "keystone-public-sample-v1")
    A._CACHED_KEY = None
    payload = {"seq": 0, "x": "y"}
    canon = A._canonical(payload)
    forged = _hmac.new(b"keystone-public-sample-v1", (A.GENESIS_PREV + canon).encode(), hashlib.sha256).hexdigest()
    assert A._row_hash(A.GENESIS_PREV, payload) == forged   # a key holder can forge a valid hash
    A._CACHED_KEY = None


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


def _fake_gitlab_oidc_token(sub="project_path:g/p:ref_type:branch:ref:main", **claims):
    import base64, json
    def b64(d): return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    payload = {"iss": "https://gitlab.com", "sub": sub, "aud": "keystone",
               "project_path": "g/p", "ref": "main", "user_login": "alice", **claims}
    return b64({"alg": "RS256", "typ": "JWT"}) + "." + b64(payload) + ".sig"


def test_ci_identity_binding_flips_self_asserted(graph, monkeypatch, tmp_path):
    # On the GitLab CI path a runner-injected OIDC token binds the actor to its `sub`
    # claim, so the recorded decision is GitLab-attested, not self-asserted.
    from core import identity as identity_mod, gate as gate_mod
    monkeypatch.setenv("KEYSTONE_ID_TOKEN", _fake_gitlab_oidc_token())
    ci = identity_mod.ci_identity()
    assert ci and ci["bound"] is True and ci["sub"].startswith("project_path:g/p")
    assert ci["signature_verified"] is False     # honest: claims bound by CI, not RS256-checked here

    led = Ledger(str(tmp_path / "id_ledger.jsonl"))
    bound = gate_mod.evaluate(graph, led, name="parse", decision="approve",
                              reviewer="alice", ci_identity=ci)
    assert bound["ok"] and bound["self_asserted"] is False
    assert bound["row_extra"]["self_asserted"] is False
    assert bound["row_extra"]["ci_identity"]["sub"] == ci["sub"]

    # without a bound identity, the same decision is honestly self-asserted
    unbound = gate_mod.evaluate(graph, led, name="parse", decision="approve", reviewer="alice")
    assert unbound["self_asserted"] is True and "ci_identity" not in unbound["row_extra"]


def test_ci_identity_absent_when_no_token(monkeypatch):
    from core import identity as identity_mod
    for v in ("KEYSTONE_ID_TOKEN", "GITLAB_OIDC_TOKEN", "CI_JOB_JWT_V2", "CI_JOB_JWT"):
        monkeypatch.delenv(v, raising=False)
    assert identity_mod.ci_identity() is None
    assert identity_mod.decode_jwt_claims("not-a-jwt") is None
