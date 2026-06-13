"""Policy-as-code governance engine (deterministic, no model, no learning).

Maps the engine-computed blast radius to a severity TIER and a concrete governance
outcome (required approver count, review window, ALLOW / HOLD / BLOCK), using a
versioned policy whose canonical sha256 is pinned into every decision. The same
graph snapshot plus the same policy always yields the same tier — this is the
enforcement decision the Orbit graph drives, not decoration.

Policy source: .keystone/policy.json if present, else the committed DEFAULT_POLICY.
Standard library only (json, hashlib). No PyYAML dependency; JSON is the policy
format so the canonical hash is unambiguous.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Optional

POLICY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".keystone", "policy.json")
POLICY_PATH = os.path.abspath(POLICY_PATH)

# Tiers are evaluated top-down: the first tier whose max_affected_files is None
# (catch-all) OR >= the change's affected-file count wins. ORG_WIDE holds.
DEFAULT_POLICY = {
    "version": "1",
    "tiers": [
        {"name": "ISOLATED",   "max_affected_files": 1,    "required_approvers": 1, "review_window_hours": 0,  "action": "ALLOW"},
        {"name": "LOCAL",      "max_affected_files": 3,    "required_approvers": 1, "review_window_hours": 4,  "action": "ALLOW"},
        {"name": "CROSS_TEAM", "max_affected_files": 8,    "required_approvers": 2, "review_window_hours": 24, "action": "ALLOW"},
        {"name": "ORG_WIDE",   "max_affected_files": None, "required_approvers": 3, "review_window_hours": 48, "action": "HOLD"},
    ],
    "block_on_identical_contradiction": True,   # a prior identical-signature rejection blocks merge
    "max_blast_radius_defs": None,              # optional hard cap on total affected definitions
    "window_enforced": False,                   # when True, the review_window_hours is a real time gate
}


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def load_policy() -> dict:
    """The active policy: the committed override if present and valid, else default."""
    if os.path.exists(POLICY_PATH):
        try:
            with open(POLICY_PATH, encoding="utf-8") as f:
                p = json.load(f)
            if isinstance(p, dict) and p.get("tiers"):
                return p
        except Exception:
            pass
    return DEFAULT_POLICY


def policy_hash(policy: Optional[dict] = None) -> str:
    """sha256 of the canonical policy JSON, pinned into every decision so an audit
    can reconstruct exactly which policy was in force."""
    return hashlib.sha256(_canonical(policy or load_policy()).encode("utf-8")).hexdigest()


def _counts(impact_dict: dict) -> dict:
    owners = impact_dict.get("owners", []) or []
    # affected = everything except the epicenter (ring 0)
    aff = [o for o in owners if o.get("ring", 0) != 0]
    files = sorted({o.get("file") for o in aff if o.get("file")})
    dirs = sorted({o.get("dir") for o in aff if o.get("dir")})
    return {
        "affected_definitions": int(impact_dict.get("counts", {}).get("total_affected", 0)),
        "affected_files": len(files),
        "affected_directories": len(dirs),
        "files": files,
        "directories": dirs,
    }


def _pick_tier(policy: dict, affected_files: int) -> dict:
    for t in policy["tiers"]:
        cap = t.get("max_affected_files")
        if cap is None or affected_files <= cap:
            return t
    return policy["tiers"][-1]


def evaluate(impact_dict: dict, precedent_dict: Optional[dict] = None,
             policy: Optional[dict] = None) -> dict:
    """Deterministically map an impact (and its precedent) to a governance outcome.

    Returns tier, raw counts (always shown alongside the label), required approvers,
    review window, action (ALLOW / HOLD / BLOCK), the reasons, the named owner to
    pull in on a HOLD, and the pinned policy version + hash. No model anywhere.
    """
    policy = policy or load_policy()
    counts = _counts(impact_dict)
    tier = _pick_tier(policy, counts["affected_files"])
    action = tier["action"]
    reasons = [f"{counts['affected_definitions']} dependent definitions across "
               f"{counts['affected_files']} files / {counts['affected_directories']} directories -> tier {tier['name']}"]

    prec = precedent_dict or {}
    if policy.get("block_on_identical_contradiction") and prec.get("contradiction_strength") == "identical":
        action = "BLOCK"
        c = prec.get("contradiction") or {}
        reasons.append(f"BLOCK: identical blast radius was rejected before ({c.get('change_id', '?')} by {c.get('actor', '?')})")

    cap = policy.get("max_blast_radius_defs")
    if cap is not None and counts["affected_definitions"] > cap:
        action = "BLOCK"
        reasons.append(f"BLOCK: blast radius {counts['affected_definitions']} exceeds policy cap {cap}")

    # named owner to pull in (the epicenter's owning directory), surfaced on HOLD/ORG_WIDE
    epi_owner = None
    for o in impact_dict.get("owners", []) or []:
        if o.get("ring", 0) == 0:
            epi_owner = o.get("dir") or o.get("file")
            break

    return {
        "tier": tier["name"],
        "action": action,                       # ALLOW | HOLD | BLOCK
        "counts": {k: counts[k] for k in ("affected_definitions", "affected_files", "affected_directories")},
        "affected_files": counts["files"],
        "affected_directories": counts["directories"],
        "required_approvers": tier["required_approvers"],
        "review_window_hours": tier["review_window_hours"],
        "required_owner": epi_owner,
        "reasons": reasons,
        "policy_version": policy.get("version", "?"),
        "policy_hash": policy_hash(policy),
    }
