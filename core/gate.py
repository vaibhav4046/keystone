"""The single governance decision, shared by the FastAPI handler and the CLI gate.

Centralizing it here means a change blocked by the API is blocked identically by
`run_review.py --local` in CI - there is no second, weaker code path. Pure and
deterministic: same graph + same ledger + same policy => same verdict. No model.

evaluate(...) returns a dict:
  blocked -> {"ok": False, "status": <http code>, "error": <code>, "detail": {...}}
  allowed -> {"ok": True, "impact", "policy", "author", "quorum", "sig",
              "change_id", "target_fqns", "blast_set", "row_extra"}
The caller appends the ledger row (so the append stays under the ledger's lock).
"""
from __future__ import annotations

import datetime
import os
import time
from typing import Optional

from . import (impact as impact_mod, policy as policy_mod, attest as attest_mod,
               agents as agents_mod, mr as mr_mod)


def _parse_ts(ts: str):
    try:
        return datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).timestamp()
    except Exception:
        return None


def opened_at(ledger, name: str, signature: str, change_id: str):
    """Earliest review timestamp for a change, reconstructed from the LEDGER (not an
    in-process dict), so the review-window gate survives a server restart."""
    epochs = []
    for r in ledger.rows():
        if (not r.get("seeded") and r.get("change_id") == change_id
                and name in (r.get("target_symbols") or []) and r.get("signature") == signature):
            e = _parse_ts(r.get("ts") or "")
            if e is not None:
                epochs.append(e)
    return min(epochs) if epochs else None


def prior_approvers(ledger, name: str, signature: str, change_id: str) -> list:
    """Distinct prior approvers that count toward quorum for ONE change: same
    change_id, excluding seeded historical rows, and only approvals AFTER the most
    recent rejection for that change (a rejection resets the count)."""
    rows = ledger.rows()                                   # newest-first
    rel = [r for r in rows if not r.get("seeded") and r.get("change_id") == change_id
           and name in (r.get("target_symbols") or []) and r.get("signature") == signature]
    last_reject = max([r["seq"] for r in rel if r.get("decision") == "reject"], default=-1)
    return sorted({r["actor"] for r in rel if r.get("decision") == "approve" and r["seq"] > last_reject})


def evaluate(graph, ledger, *, name: str, decision: str, reviewer: str,
             change_id: Optional[str] = None, change_author: Optional[str] = None,
             author_kind: Optional[str] = None, override: bool = False,
             max_depth: int = 3, policy: Optional[dict] = None,
             registry: Optional[dict] = None, ci_identity: Optional[dict] = None) -> dict:
    imp = impact_mod.compute_blast_radius(graph, name, max_depth=max_depth)
    if imp is None:
        return {"ok": False, "status": 404, "error": "NOT_FOUND",
                "detail": {"error": "NOT_FOUND", "message": f"definition not found: {name}"}}
    out = imp.to_dict()
    fqns = [imp.epicenter_fqn] if imp.epicenter_fqn else None
    prec = ledger.precedent(target_symbols=[name], signature=imp.signature, target_fqns=fqns)
    pol = policy_mod.evaluate(out, prec, policy)
    out["policy"] = pol
    out["orbit_snapshot_sha256"] = attest_mod.orbit_snapshot_sha256(out)

    # Bound-identity enforcement (T-4). On the GitLab OIDC path the actor IS the token's claim, so
    # a client-supplied reviewer that disagrees with the bound identity is rejected (you cannot
    # approve as someone else). And when KEYSTONE_STRICT_OVERRIDE is set, an override is refused
    # unless the actor is cryptographically bound, so an override is never a self-asserted bypass.
    bound = bool(ci_identity and ci_identity.get("bound"))
    if bound and reviewer and reviewer not in (ci_identity.get("actor"), ci_identity.get("sub")):
        return {"ok": False, "status": 403, "error": "IDENTITY_MISMATCH",
                "detail": {"error": "IDENTITY_MISMATCH",
                           "bound": ci_identity.get("actor") or ci_identity.get("sub"),
                           "hint": "the reviewer must match the bound OIDC identity on the CI path"}}
    if (decision == "approve" and override and not bound and os.environ.get("KEYSTONE_STRICT_OVERRIDE")):
        return {"ok": False, "status": 403, "error": "OVERRIDE_REQUIRES_IDENTITY",
                "detail": {"error": "OVERRIDE_REQUIRES_IDENTITY",
                           "hint": "KEYSTONE_STRICT_OVERRIDE is set: an override requires a cryptographically bound identity (GitLab OIDC), not a self-asserted reviewer"}}

    author = agents_mod.resolve_author(reviewer, declared_kind=author_kind, registry=registry)
    scope = agents_mod.check_scope(author, out)
    if not scope["in_scope"]:
        return {"ok": False, "status": 403, "error": "SCOPE_VIOLATION",
                "detail": {"error": "SCOPE_VIOLATION", "author": author, "violations": scope["violations"]}}
    if decision == "approve" and author["badge"] == "AGENT_UNREGISTERED":
        return {"ok": False, "status": 403, "error": "UNREGISTERED_AGENT",
                "detail": {"error": "UNREGISTERED_AGENT", "author": author,
                           "hint": "register this agent in .keystone/agents.json or have a human review"}}
    # four-eyes: the author of a change cannot approve their own change (without override)
    if decision == "approve" and change_author and reviewer == change_author and not override:
        return {"ok": False, "status": 403, "error": "SELF_APPROVAL",
                "detail": {"error": "SELF_APPROVAL", "change_author": change_author,
                           "hint": "the change author cannot approve their own change; a different reviewer or an override is required"}}
    if decision == "approve" and pol["action"] == "BLOCK" and not override:
        return {"ok": False, "status": 409, "error": "GOVERNANCE_BLOCK",
                "detail": {"error": "GOVERNANCE_BLOCK", "reasons": pol["reasons"], "policy": pol,
                           "hint": "set override=true with a rationale to record an accountable override"}}

    cid = change_id or f"KS-{name}"
    prior = prior_approvers(ledger, name, imp.signature, cid)
    confirmed = sorted(set(prior) | ({reviewer} if decision == "approve" else set()))
    required = pol["required_approvers"]
    if decision == "reject":
        quorum_status = "REJECTED"
    elif len(confirmed) >= required:
        quorum_status = "APPROVED"
    else:
        quorum_status = "PENDING_APPROVAL"

    # Time-window gate (restart-safe): enforced only when the active policy opts in.
    active = policy or policy_mod.load_policy()
    window_h = pol.get("review_window_hours")
    if (decision == "approve" and quorum_status == "APPROVED" and not override
            and window_h and active.get("window_enforced")):
        opened = opened_at(ledger, name, imp.signature, cid)
        if opened is not None and (time.time() - opened) < window_h * 3600:
            remaining = round((window_h * 3600 - (time.time() - opened)) / 3600, 2)
            return {"ok": False, "status": 409, "error": "REVIEW_WINDOW_PENDING",
                    "detail": {"error": "REVIEW_WINDOW_PENDING", "time_remaining_hours": remaining,
                               "review_window_hours": window_h}}

    # Identity binding: on the GitLab CI path a runner-injected OIDC token binds the actor
    # to a `sub` claim, so the decision is GitLab-attested rather than self-asserted. The
    # flag is the honest discriminator auditors key on; it is only flipped when a real bound
    # identity is supplied (never by a free-typed reviewer string).
    bound = bool(ci_identity and ci_identity.get("bound"))
    self_asserted = not bound
    # An override is load-bearing (and must be recorded in the immutable row) when it actually
    # bypassed a gate: a policy BLOCK, or the four-eyes self-approval check. A gratuitous
    # override on a clean approval is not recorded, so the flag never overstates or hides.
    override_used = bool(override) and (
        pol["action"] == "BLOCK"
        or (decision == "approve" and bool(change_author) and reviewer == change_author)
    )
    row_extra = {
        "tier": pol["tier"], "governance_action": pol["action"],
        "policy_version": pol["policy_version"], "policy_hash": pol["policy_hash"],
        "orbit_snapshot_sha256": out["orbit_snapshot_sha256"], "author_kind": author["badge"],
        "required_approvers": required, "confirmed_approvers": confirmed,
        "quorum_status": quorum_status, "override": override_used,
        # honest: the actor is self-asserted unless bound to GitLab OIDC; auditors can
        # distinguish advisory from cryptographically-bound decisions on this flag.
        "self_asserted": self_asserted,
    }
    if bound:
        # record the bound subject + issuer (non-sensitive subset) for the audit trail
        row_extra["ci_identity"] = {k: ci_identity.get(k) for k in
                                    ("source", "sub", "iss", "project_path", "ref", "signature_verified")}
    if change_author:
        row_extra["change_author"] = change_author
    return {
        "ok": True, "impact": out, "policy": pol, "author": author,
        "self_asserted": self_asserted, "ci_identity": ci_identity if bound else None,
        "quorum": {"required": required, "confirmed": len(confirmed), "status": quorum_status,
                   "closed": quorum_status == "APPROVED",   # 200 != closed; check this flag
                   "approvers": confirmed, "change_id": cid},
        "sig": imp.signature, "change_id": cid, "target_fqns": fqns,
        "blast_set": imp.affected_ids, "row_extra": row_extra,
    }


def evaluate_mr(graph, ledger, *, names, decision: str, reviewer: str,
                change_id: Optional[str] = None, change_author: Optional[str] = None,
                author_kind: Optional[str] = None,
                override: bool = False, max_depth: int = 3, policy: Optional[dict] = None,
                registry: Optional[dict] = None,
                ci_identity: Optional[dict] = None) -> dict:
    """Govern and RECORD a decision against a whole merge request (several touched symbols), bound
    to the MR signature and the full touched-symbol set rather than one epicenter. Applies the same
    governance as the single-symbol gate -- an identical-signature contradiction forces BLOCK,
    four-eyes, an accountable override, bound-identity checks, and a per-change quorum -- so a
    multi-symbol MR is recorded as the real unit it is. The caller appends the returned row."""
    mr_res = mr_mod.compute_mr_impact(graph, list(names or []), max_depth=max_depth)
    if mr_res is None:
        return {"ok": False, "status": 404, "error": "NOT_FOUND",
                "detail": {"error": "NOT_FOUND", "message": "none of the MR symbols resolve in the graph"}}
    union = mr_res["union"]
    impact_dict = mr_res.get("impact_dict") or {}        # union impact context (epicenter + affected set)
    sig = union["signature"]
    target_symbols = mr_res["resolved"]
    target_fqns = [f for f in (mr_res.get("epicenter_fqns") or []) if f] or None
    prec = ledger.precedent(target_symbols=target_symbols, signature=sig, target_fqns=target_fqns)

    active = policy or policy_mod.load_policy()
    action = union["action"]
    reasons = list(union.get("reasons") or [])
    if active.get("block_on_identical_contradiction") and prec.get("contradiction_strength") == "identical":
        action = "BLOCK"
        c = prec.get("contradiction") or {}
        reasons.append(f"BLOCK: an identical MR blast radius was rejected before "
                       f"({c.get('change_id', '?')} by {c.get('actor', '?')})")

    bound = bool(ci_identity and ci_identity.get("bound"))
    if bound and reviewer and reviewer not in (ci_identity.get("actor"), ci_identity.get("sub")):
        return {"ok": False, "status": 403, "error": "IDENTITY_MISMATCH",
                "detail": {"error": "IDENTITY_MISMATCH", "bound": ci_identity.get("actor") or ci_identity.get("sub")}}
    if decision == "approve" and override and not bound and os.environ.get("KEYSTONE_STRICT_OVERRIDE"):
        return {"ok": False, "status": 403, "error": "OVERRIDE_REQUIRES_IDENTITY",
                "detail": {"error": "OVERRIDE_REQUIRES_IDENTITY"}}
    # Resolve the author the same way `evaluate` does, so the recorded `author_kind` reflects a
    # real human / registered-agent / unregistered-agent badge rather than a hardcoded "human".
    # This keeps the audit trail honest: an MR rubber-stamped by an unregistered agent must not
    # be recorded as a human decision. Scope is checked against the union's affected file set,
    # because the MR is the union of every touched symbol's blast.
    author = agents_mod.resolve_author(reviewer, declared_kind=author_kind, registry=registry)
    scope = agents_mod.check_scope(author, impact_dict)
    if not scope["in_scope"]:
        return {"ok": False, "status": 403, "error": "SCOPE_VIOLATION",
                "detail": {"error": "SCOPE_VIOLATION", "author": author, "violations": scope["violations"]}}
    if decision == "approve" and author["badge"] == "AGENT_UNREGISTERED":
        return {"ok": False, "status": 403, "error": "UNREGISTERED_AGENT",
                "detail": {"error": "UNREGISTERED_AGENT", "author": author,
                           "hint": "register this agent in .keystone/agents.json or have a human review"}}
    if decision == "approve" and change_author and reviewer == change_author and not override:
        return {"ok": False, "status": 403, "error": "SELF_APPROVAL",
                "detail": {"error": "SELF_APPROVAL", "change_author": change_author}}
    if decision == "approve" and action == "BLOCK" and not override:
        return {"ok": False, "status": 409, "error": "GOVERNANCE_BLOCK",
                "detail": {"error": "GOVERNANCE_BLOCK", "reasons": reasons,
                           "hint": "set override=true with a rationale to record an accountable override"}}

    cid = change_id or ("KS-MR-" + "+".join(sorted(target_symbols)))
    # Quorum over the MR: distinct approvers of the same change_id + MR signature, counted only
    # after the most recent rejection (a rejection resets the count), mirroring the single gate.
    rows = ledger.rows()
    rel = [r for r in rows if not r.get("seeded") and r.get("change_id") == cid and r.get("signature") == sig]
    last_reject = max([r["seq"] for r in rel if r.get("decision") == "reject"], default=-1)
    prior = sorted({r["actor"] for r in rel if r.get("decision") == "approve" and r["seq"] > last_reject})
    confirmed = sorted(set(prior) | ({reviewer} if decision == "approve" else set()))
    required = union["required_approvers"]
    quorum_status = ("REJECTED" if decision == "reject"
                     else ("APPROVED" if len(confirmed) >= required else "PENDING_APPROVAL"))

    self_asserted = not bound
    override_used = bool(override) and (action == "BLOCK"
                                        or (decision == "approve" and bool(change_author) and reviewer == change_author))
    row_extra = {
        "tier": union["tier"], "governance_action": action,
        "policy_version": union["policy_version"], "policy_hash": union["policy_hash"],
        "orbit_snapshot_sha256": union["orbit_snapshot_sha256"],
        # Honest: resolve the author through the agent registry so the recorded badge reflects
        # a real human / registered-agent / unregistered-agent, mirroring the single-symbol path.
        "author_kind": author["badge"],
        "required_approvers": required, "confirmed_approvers": confirmed,
        "quorum_status": quorum_status, "override": override_used, "self_asserted": self_asserted,
        "mr": True, "mr_symbols": target_symbols,
    }
    if bound:
        row_extra["ci_identity"] = {k: ci_identity.get(k) for k in
                                    ("source", "sub", "iss", "project_path", "ref", "signature_verified")}
    if change_author:
        row_extra["change_author"] = change_author
    return {
        "ok": True, "union": union, "per_symbol": mr_res["per_symbol"], "reasons": reasons,
        "author": author, "self_asserted": self_asserted,
        "ci_identity": ci_identity if bound else None,
        "quorum": {"required": required, "confirmed": len(confirmed), "status": quorum_status,
                   "closed": quorum_status == "APPROVED", "approvers": confirmed, "change_id": cid},
        "sig": sig, "change_id": cid, "target_symbols": target_symbols, "target_fqns": target_fqns,
        "blast_set": union.get("affected_ids") or [], "row_extra": row_extra,
        # The impact_dict used to derive the orbit_snapshot_sha256 - the attestation builder
        # needs it to bind the attestation to the exact union context the reviewer was shown.
        # This is the dict that would NOT roundtrip from a single-symbol lookup.
        "impact_dict": impact_dict,
    }
