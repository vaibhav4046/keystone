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
        return False, "unparseable exp"      # a present-but-malformed exp must fail closed, not bind as never-expiring
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


# ---------------------------------------------------------------------------
# Self-contained cryptographic reviewer identity (Ed25519) - NO external service.
#
# The OIDC path above binds identity to a GitLab runner, which needs a GitLab Ultimate/CI
# environment. This path needs nothing but local crypto: a reviewer holds an Ed25519 private
# key, registers the PUBLIC key in .keystone/reviewers.json, and signs each decision. Keystone
# verifies the signature against the registered public key, so the recorded actor is proven by
# possession of a key (the same model as a signed Git commit / SSH / Sigstore), not self-asserted -
# and the proof is recorded into the tamper-evident ledger. Offline, deterministic, no account.
# ---------------------------------------------------------------------------

def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def signing_payload(actor: str, change_id: str, decision: str, symbols) -> dict:
    """The exact, canonical object a reviewer signs - binds the signature to WHO + WHAT + the
    verdict, so a signature cannot be replayed onto a different change, symbol set, or decision."""
    return {"actor": actor, "change_id": change_id or "", "decision": decision,
            "symbols": sorted(str(s) for s in (symbols or []))}


def _reviewers_path() -> str:
    env = os.environ.get("KEYSTONE_REVIEWERS")
    if env:
        return env
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(here, ".keystone", "reviewers.json")


def load_reviewer_keys(path: Optional[str] = None) -> dict:
    """reviewer_id -> Ed25519 public key (hex), from .keystone/reviewers.json ({"reviewers": {...}})."""
    path = path or _reviewers_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        keys = data.get("reviewers", data) if isinstance(data, dict) else {}
        return {k: v for k, v in keys.items() if isinstance(v, str)}
    except (OSError, ValueError):
        return {}


def generate_keypair() -> tuple:
    """(private_hex, public_hex) for a fresh Ed25519 reviewer key. For keygen / demo / tests."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    priv_raw = priv.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                  serialization.NoEncryption())
    pub_raw = pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return priv_raw.hex(), pub_raw.hex()


def sign_decision(private_hex: str, payload: dict) -> str:
    """Ed25519 signature (hex) over the canonical signing payload. The reviewer's local action."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_hex))
    return priv.sign(_canonical(payload)).hex()


def verify_decision_signature(public_hex: str, payload: dict, signature_hex: str) -> bool:
    """True iff signature_hex is a valid Ed25519 signature over canonical(payload) under public_hex.
    Never raises, never overstates: returns False if cryptography is absent or anything is malformed."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
    except Exception:
        return False
    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_hex))
        pub.verify(bytes.fromhex(signature_hex), _canonical(payload))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False
    except Exception:
        return False


def signed_identity(actor: str, change_id: str, decision: str, symbols, signature_hex: str,
                    registry: Optional[dict] = None) -> Optional[dict]:
    """If `actor` has a registered Ed25519 public key and signature_hex verifies over the canonical
    signing payload, return a BOUND identity dict (cryptographically proven, not self-asserted);
    otherwise None (the caller falls back to the self-asserted path or rejects)."""
    keys = registry if registry is not None else load_reviewer_keys()
    pub = keys.get(actor)
    if not pub:
        return None
    payload = signing_payload(actor, change_id, decision, symbols)
    if not verify_decision_signature(pub, payload, signature_hex):
        return None
    return {
        "bound": True,
        "source": "ed25519-signature",
        "actor": actor,
        "signature_verified": True,
        "public_key": pub,
        "note": "actor proven by an Ed25519 signature over the decision, verified against the "
                "registered public key (no external service); recorded in the tamper-evident ledger",
    }


__all__ = ["ci_identity", "decode_jwt_claims", "verify_signature", "signing_payload",
           "load_reviewer_keys", "generate_keypair", "sign_decision",
           "verify_decision_signature", "signed_identity"]
