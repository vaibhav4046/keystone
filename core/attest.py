"""Decision attestations: serialize an approved/rejected decision as a standards-
shaped, machine-checkable artifact (in-toto Statement v1 with a SLSA Verification
Summary-style predicate), anchored to the exact Orbit graph context the reviewer saw.

Honesty rules (no overclaiming):
  - Keystone-issued. It is NOT a SLSA conformance body; the predicate says so.
  - Integrity is the HMAC hash chain, not a cryptographic signature. Sigstore/Rekor
    keyless signing is a documented future step and is explicitly marked false here.
  - orbit_snapshot_sha256 binds the decision to the precise graph-derived context
    (epicenter, rings, affected set, owners, signature), so the attestation proves
    which Orbit picture drove the approval - the gap SLSA/in-toto leave open.
  - Read-only serialization of already-committed deterministic facts. No model.

Standard library only.
"""
from __future__ import annotations

import hashlib
import json
from typing import Optional

STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://slsa.dev/verification_summary/v1"


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def orbit_snapshot_sha256(impact_dict: dict) -> str:
    """sha256 over the exact Orbit-derived context the reviewer was shown."""
    ctx = {
        "epicenter": impact_dict.get("epicenter"),
        "affected_ids": impact_dict.get("affected_ids"),
        "rings": impact_dict.get("rings"),
        "signature": impact_dict.get("signature"),
        "counts": impact_dict.get("counts"),
        "owners": impact_dict.get("owners"),
    }
    return hashlib.sha256(_canonical(ctx).encode("utf-8")).hexdigest()


def build_attestation(*, impact_dict: dict, policy_eval: dict, row: dict, source_mode: str) -> dict:
    """An in-toto Statement carrying a SLSA-VSA-style predicate for one decision."""
    snap = orbit_snapshot_sha256(impact_dict)
    epi = impact_dict.get("epicenter", {}) or {}
    qstatus = row.get("quorum_status")
    if qstatus == "APPROVED":
        result = "PASSED"
    elif qstatus == "PENDING_APPROVAL":
        result = "PENDING"
    elif qstatus == "REJECTED":
        result = "FAILED"
    else:
        result = "PASSED" if row.get("decision") == "approve" else "FAILED"
    return {
        "_type": STATEMENT_TYPE,
        "predicateType": PREDICATE_TYPE,
        "subject": [{
            "name": epi.get("fqn") or epi.get("name") or "?",
            "digest": {"sha256": snap},
        }],
        "predicate": {
            "verifier": {"id": "keystone", "note": "Keystone-issued attestation; not a SLSA conformance body"},
            "timeVerified": row.get("ts"),
            "policy": {"version": policy_eval.get("policy_version"),
                       "sha256": policy_eval.get("policy_hash"), "uri": ".keystone/policy.json"},
            "verificationResult": result,
            "decision": row.get("decision"),
            "quorumStatus": qstatus,
            "confirmedApprovers": row.get("confirmed_approvers"),
            "override": row.get("override", False),
            "reviewer": row.get("actor"),
            "reviewerKind": row.get("author_kind", "human"),
            "changeId": row.get("change_id"),
            "targetSymbols": row.get("target_symbols"),
            "targetFqns": row.get("target_fqns"),
            "blastRadius": policy_eval.get("counts"),
            "tier": policy_eval.get("tier"),
            "governanceAction": policy_eval.get("action"),
            "requiredApprovers": policy_eval.get("required_approvers"),
            "reviewWindowHours": policy_eval.get("review_window_hours"),
            "blastSignature": impact_dict.get("signature"),
            "orbitSnapshotSha256": snap,
            "orbitSourceMode": source_mode,           # LIVE or FALLBACK, disclosed
            "ledger": {"seq": row.get("seq"), "rowHash": row.get("row_hash"), "prevHash": row.get("prev_hash")},
            "integrity": {
                "hmacChained": True,
                "sigstore": False,
                "rekorLogIndex": None,
                "note": "tamper-evident via an HMAC-keyed sha256 hash chain; Sigstore/Rekor "
                        "keyless signing is a documented future step and is not claimed here",
            },
        },
    }


def verify_attestation(att: dict, ledger) -> dict:
    """Offline verification: the chain is intact AND the attestation's referenced
    ledger row hash is present in it. Returns {ok, chain_ok, row_present, reason}."""
    v = ledger.verify()
    try:
        row_hash = att["predicate"]["ledger"]["rowHash"]
    except Exception:
        return {"ok": False, "chain_ok": v["ok"], "row_present": False, "reason": "malformed attestation"}
    present = any(r.get("row_hash") == row_hash for r in ledger.rows())
    ok = bool(v["ok"] and present)
    reason = "ok" if ok else ("chain broken" if not v["ok"] else "row hash not found in ledger")
    return {"ok": ok, "chain_ok": v["ok"], "row_present": present, "reason": reason}
