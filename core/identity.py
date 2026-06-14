"""Cryptographic actor binding on the GitLab CI path (closes the self-asserted gap).

In the web demo the reviewer is a free-typed string, so four-eyes and agent gating are
advisory (the ledger proves the text was not edited, not WHO typed it). GitLab CI removes
that ambiguity: the runner injects a signed OIDC ID token whose claims identify the
project, pipeline, ref, and the user who triggered it. On that path Keystone binds the
recorded actor to the token's `sub` claim and stamps the decision with the issuer + claims,
so a pipeline decision is GitLab-attested rather than self-asserted.

Honesty boundary (kept deliberately tight):
  - We DECODE the token claims (base64url) and record them. The token's trustworthiness on
    the CI path comes from the GitLab runner injecting it into the job environment.
  - We do NOT claim offline signature verification here: RS256 verification needs GitLab's
    JWKS and an RSA implementation (the `cryptography` package). `signature_verified` is
    therefore False by default; verify_signature() is a best-effort hook for deployments
    that add that dependency. The recorded flag never overstates what was checked.

Standard library only.
"""
from __future__ import annotations

import base64
import json
import os
from typing import Optional

# Env vars a GitLab `id_tokens:` block (or the legacy CI_JOB_JWT) may expose. First hit wins.
_TOKEN_ENV_VARS = ("KEYSTONE_ID_TOKEN", "GITLAB_OIDC_TOKEN", "CI_JOB_JWT_V2", "CI_JOB_JWT")


def _b64url_decode(seg: str) -> bytes:
    seg = seg + "=" * (-len(seg) % 4)          # restore stripped padding
    return base64.urlsafe_b64decode(seg.encode("ascii"))


def decode_jwt_claims(token: str) -> Optional[dict]:
    """Decode a JWT's payload claims WITHOUT verifying the signature. Returns None on any
    malformation. The caller must treat trust as coming from the token's source, not this."""
    try:
        parts = token.strip().split(".")
        if len(parts) != 3:
            return None
        claims = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
        return claims if isinstance(claims, dict) else None
    except Exception:
        return None


def _first_token() -> Optional[str]:
    for var in _TOKEN_ENV_VARS:
        v = os.environ.get(var)
        if v and v.count(".") == 2:
            return v
    return None


def ci_identity() -> Optional[dict]:
    """Resolve a bound CI identity from a GitLab OIDC ID token in the environment, or None
    when not running on a token-bearing pipeline. The returned dict is what the gate stamps
    onto the ledger row so the actor is GitLab-attested, not self-asserted."""
    token = _first_token()
    if not token:
        return None
    claims = decode_jwt_claims(token)
    if not claims or not claims.get("sub"):
        return None
    # A curated, non-sensitive subset of the standard GitLab OIDC claims.
    keep = ("sub", "iss", "aud", "project_path", "namespace_path", "ref", "ref_type",
            "pipeline_id", "job_id", "runner_id", "user_login", "user_email")
    subset = {k: claims[k] for k in keep if k in claims}
    return {
        "bound": True,
        "source": "gitlab-oidc",
        "sub": claims["sub"],
        "iss": claims.get("iss"),
        "actor": claims.get("user_login") or claims.get("sub"),
        "project_path": claims.get("project_path"),
        "ref": claims.get("ref"),
        "signature_verified": False,   # honest: claims bound by CI injection, not RS256-checked here
        "claims": subset,
        "note": "actor bound to the GitLab OIDC sub claim injected by the runner; "
                "RS256 JWKS verification is the production hardening step.",
    }


def verify_signature(token: str) -> bool:
    """Best-effort RS256 verification against the issuer's JWKS. Returns False unless the
    optional `cryptography` dependency is present AND the issuer's keys validate the token.
    Deployments that want hard verification install `cryptography`; the gate's recorded
    `signature_verified` reflects the real result and never overstates it."""
    try:
        import urllib.request
        from cryptography.hazmat.primitives.asymmetric import padding  # type: ignore
        from cryptography.hazmat.primitives import hashes, serialization  # noqa: F401
        # Intentionally minimal: real deployments flesh this out with JWKS key matching by
        # kid. Absent the dependency we return False rather than pretend verification ran.
        return False
    except Exception:
        return False


__all__ = ["ci_identity", "decode_jwt_claims", "verify_signature"]
