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


def test_agent_scope_governs_changed_file_not_affected_dependents():
    """An agent's path scope must govern what it CHANGES (the ring-0 epicenter), not a
    transitive dependent that merely lives in a forbidden path. Changing an allowed file whose
    blast reaches a forbidden dependent is in-scope (the dependent is never edited); magnitude
    is governed by max_blast_radius, not the path rule. Changing a file IN a forbidden path is
    still a violation."""
    reg = {"agents": {"bot": {"allowed_paths": ["src/parser/**"],
                              "forbidden_paths": ["src/cli/**"], "max_blast_radius": 99}}}
    bot = agents_mod.resolve_author("bot", declared_kind="agent", registry=reg)
    changes_allowed_affects_forbidden = {
        "owners": [{"ring": 0, "file": "src/parser/lexer.py"},
                   {"ring": 1, "file": "src/cli/main.py"}],
        "counts": {"total_affected": 1}}
    assert agents_mod.check_scope(bot, changes_allowed_affects_forbidden)["in_scope"] is True
    changes_forbidden = {"owners": [{"ring": 0, "file": "src/cli/main.py"}],
                         "counts": {"total_affected": 0}}
    assert agents_mod.check_scope(bot, changes_forbidden)["in_scope"] is False


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
    its chain is illustrative only - anyone holding the published key reproduces a
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


def _mint_rs256(claims, kid="k1"):
    """Mint a genuinely RS256-signed JWT + the matching JWK, so RS256 verification can be
    proven end-to-end offline (no network, no pinned GitLab key)."""
    import base64, json
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives import hashes
    def b64u(b): return base64.urlsafe_b64encode(b).decode().rstrip("=")
    def seg(d): return b64u(json.dumps(d, separators=(",", ":")).encode())
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pn = key.public_key().public_numbers()
    def itob(i): return i.to_bytes((i.bit_length() + 7) // 8, "big")
    jwk = {"kty": "RSA", "kid": kid, "n": b64u(itob(pn.n)), "e": b64u(itob(pn.e))}
    signing_input = (seg({"alg": "RS256", "typ": "JWT", "kid": kid}) + "." + seg(claims)).encode("ascii")
    sig = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    token = signing_input.decode("ascii") + "." + b64u(sig)
    return token, jwk


def test_rs256_signature_verification_offline(monkeypatch):
    # Prove the RS256 path really verifies a signature (closes the prior "claims bound by
    # CI injection but not cryptographically verified" gap), without any network.
    import json
    from core import identity as identity_mod
    claims = {"iss": "https://gitlab.example", "sub": "project_path:g/p:ref:main", "user_login": "alice"}
    token, jwk = _mint_rs256(claims)
    # a correctly-signed token verifies against its JWK
    assert identity_mod.verify_signature(token, jwks=[jwk]) is True
    # a tampered payload fails verification
    head, body, sig = token.split(".")
    tampered = head + "." + body[:-2] + ("AA" if not body.endswith("AA") else "BB") + "." + sig
    assert identity_mod.verify_signature(tampered, jwks=[jwk]) is False
    # ci_identity with a pinned JWKS flips signature_verified to true
    monkeypatch.setenv("KEYSTONE_ID_TOKEN", token)
    monkeypatch.setenv("KEYSTONE_OIDC_JWKS", json.dumps({"keys": [jwk]}))
    ci = identity_mod.ci_identity()
    assert ci and ci["signature_verified"] is True and ci["sub"] == claims["sub"]


def test_collision_merge_order_is_directional(graph):
    # if MR-hub changes a symbol and MR-caller changes a DIRECT CALLER of it (the caller
    # depends on the hub), the safe merge order must put MR-hub FIRST so the caller can be
    # re-reviewed against the change it relies on. (Regression: the edge direction was once
    # inverted, which would have told you to merge the dependent first.)
    from core import collision
    hub = graph.find_definition("serialize")
    callers = graph.direct_callers(hub["id"])
    assert callers, "serialize should have callers in the fixture"
    caller_name = graph.name_of(callers[0])
    out = collision.detect_collisions(graph, [
        {"id": "MR-hub", "symbols": ["serialize"]},
        {"id": "MR-caller", "symbols": [caller_name]}])
    assert out is not None and out["collisions"], "a hub and its caller must collide"
    if not out["uncoordinable_cycle"]:
        order = out["merge_order"]
        assert order.index("MR-hub") < order.index("MR-caller"), (caller_name, order)


def test_review_debt_untested_flag_is_graph_derived(graph):
    from core import graph_audit
    rep = graph_audit.review_debt_report(graph, limit=10)
    assert rep["hazard"] == "review_debt" and rep["items"]
    for r in rep["items"]:
        assert r["untested"] == (r["test_callers"] == 0)
        assert r["blast"] >= 2
    # the fixture has no test files, so audit_log (the 13-caller ORG_WIDE hub) is the
    # top untested review-debt hazard, and no test definition appears in the ranked set.
    names = [r["name"] for r in rep["items"]]
    top = rep["items"][0]
    assert top["name"] == "audit_log" and top["untested"] and top["blast"] == 13
    assert not any(n.startswith("test_") for n in names)


def test_is_test_path_predicate_contract(graph):
    # the 'untested' classification rests on this predicate; pin its contract so a future
    # edit can't silently widen or narrow what counts as a test file.
    con = graph._con
    cases = {"tests/test_x.py": True, "test/util.py": True, "src/test/foo.py": True,
             "src/tests/foo.py": True, "test_helpers.py": True, "core/graph.py": False,
             "backend/app.py": False, "web/app.js": False}
    for path, expected in cases.items():
        lit = "'" + path.replace("'", "''") + "'"        # safe literal; paths are fixed test data
        got = con.execute(f"SELECT {graph._is_test_path(lit)}").fetchone()[0]
        assert bool(got) is expected, (path, got)
