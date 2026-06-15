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


def _validate_claims(claims: dict) -> tuple:
    """Reject a token that is expired, for a different audience, or from an untrusted issuer.
    `exp` is always enforced when present (a runner-injected token is fresh, but a replayed or
    stale token must not bind). `aud` and `iss` are enforced only when KEYSTONE_OIDC_AUD /
    KEYSTONE_OIDC_ISS are configured, so the open demo still binds without extra setup."""
    import time
    exp = claims.get("exp")
    try:
        if exp is not None and time.time() >= float(exp):
            return False, "token expired"
    except (TypeError, ValueError):
        pass
    want_aud = os.environ.get("KEYSTONE_OIDC_AUD")
    if want_aud:
        aud = claims.get("aud")
        auds = aud if isinstance(aud, list) else [aud]
        if want_aud not in auds:
            return False, "audience mismatch"
    iss_allow = os.environ.get("KEYSTONE_OIDC_ISS")
    if iss_allow:
        allowed = {s.strip() for s in iss_allow.split(",") if s.strip()}
        if claims.get("iss") not in allowed:
            return False, "issuer not allowed"
    return True, "ok"


def ci_identity() -> Optional[dict]:
    """Resolve a bound CI identity from a GitLab OIDC ID token in the environment, or None
    when not running on a token-bearing pipeline. The returned dict is what the gate stamps
    onto the ledger row so the actor is GitLab-attested, not self-asserted.

    The token's RS256 signature is verified against the issuer's JWKS when verification is
    enabled (KEYSTONE_VERIFY_OIDC=1, or a pinned KEYSTONE_OIDC_JWKS for an air-gapped
    runner). `signature_verified` reflects the REAL result and never overstates it: claims
    are always bound by the runner injecting the token; the boolean adds cryptographic proof
    of the issuer's signature when checked."""
    token = _first_token()
    if not token:
        return None
    claims = decode_jwt_claims(token)
    if not claims or not claims.get("sub"):
        return None
    ok, why = _validate_claims(claims)
    if not ok:
        return None                      # expired / wrong audience / untrusted issuer -> not bound
    verified = False
    if os.environ.get("KEYSTONE_VERIFY_OIDC") or os.environ.get("KEYSTONE_OIDC_JWKS"):
        verified = verify_signature(token)
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
        "signature_verified": bool(verified),
        "claims": subset,
        "note": ("actor bound to the GitLab OIDC sub claim injected by the runner"
                 + (", RS256 signature verified against the issuer JWKS" if verified
                    else "; set KEYSTONE_VERIFY_OIDC=1 (or pin KEYSTONE_OIDC_JWKS) for RS256 verification")),
    }


def _rsa_pub_from_jwk(jwk: dict):
    """Build an RSA public key from a JWK (n, e). Raises if cryptography is absent."""
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
    n = int.from_bytes(_b64url_decode(jwk["n"]), "big")
    e = int.from_bytes(_b64url_decode(jwk["e"]), "big")
    return RSAPublicNumbers(e, n).public_key()


def _resolve_jwks(token: str, timeout: float) -> Optional[list]:
    """The signing keys to check against: a pinned KEYSTONE_OIDC_JWKS (air-gapped /
    deterministic tests), else the issuer's published JWKS via its discovery document."""
    pinned = os.environ.get("KEYSTONE_OIDC_JWKS")
    if pinned:
        try:
            return (json.loads(pinned) or {}).get("keys")
        except Exception:
            return None
    claims = decode_jwt_claims(token) or {}
    iss = claims.get("iss")
    if not iss:
        return None
    try:
        import urllib.request
        disc = iss.rstrip("/") + "/.well-known/openid-configuration"
        with urllib.request.urlopen(disc, timeout=timeout) as r:
            jwks_uri = json.loads(r.read().decode("utf-8")).get("jwks_uri")
        with urllib.request.urlopen(jwks_uri, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8")).get("keys")
    except Exception:
        return None


def verify_signature(token: str, *, jwks: Optional[list] = None, timeout: float = 5.0) -> bool:
    """RS256 verification of the token against the issuer's JWKS. Returns True only when the
    signature genuinely validates. Returns False (never raises, never overstates) if the
    `cryptography` dependency is absent, the keys cannot be resolved, the alg is not RS256,
    or the signature does not check out. Pass `jwks` (a list of JWK dicts) for a pinned,
    network-free check."""
    try:
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives import hashes
        from cryptography.exceptions import InvalidSignature
    except Exception:
        return False
    try:
        parts = token.strip().split(".")
        if len(parts) != 3:
            return False
        header = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
        if header.get("alg") != "RS256":
            return False
        keys = jwks if jwks is not None else _resolve_jwks(token, timeout)
        if not keys:
            return False
        kid = header.get("kid")
        jwk = next((k for k in keys if k.get("kid") == kid), None) or (keys[0] if len(keys) == 1 else None)
        if not jwk:
            return False
        pub = _rsa_pub_from_jwk(jwk)
        signing_input = (parts[0] + "." + parts[1]).encode("ascii")
        sig = _b64url_decode(parts[2])
        pub.verify(sig, signing_input, padding.PKCS1v15(), hashes.SHA256())
        return True
    except InvalidSignature:
        return False
    except Exception:
        return False


__all__ = ["ci_identity", "decode_jwt_claims", "verify_signature"]
