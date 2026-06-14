"""The single governance decision, shared by the FastAPI handler and the CLI gate.

Centralizing it here means a change blocked by the API is blocked identically by
`run_review.py --local` in CI — there is no second, weaker code path. Pure and
deterministic: same graph + same ledger + same policy => same verdict. No model.

evaluate(...) returns a dict:
  blocked -> {"ok": False, "status": <http code>, "error": <code>, "detail": {...}}
  allowed -> {"ok": True, "impact", "policy", "author", "quorum", "sig",
              "change_id", "target_fqns", "blast_set", "row_extra"}
The caller appends the ledger row (so the append stays under the ledger's lock).
"""
from __future__ import annotations

import datetime
import time
from typing import Optional

from . import impact as impact_mod, policy as policy_mod, attest as attest_mod, agents as agents_mod


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
             registry: Optional[dict] = None) -> dict:
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

    row_extra = {
        "tier": pol["tier"], "governance_action": pol["action"],
        "policy_version": pol["policy_version"], "policy_hash": pol["policy_hash"],
        "orbit_snapshot_sha256": out["orbit_snapshot_sha256"], "author_kind": author["badge"],
        "required_approvers": required, "confirmed_approvers": confirmed,
        "quorum_status": quorum_status, "override": bool(override and pol["action"] == "BLOCK"),
        # honest: the actor is self-asserted unless bound to GitLab OIDC; auditors can
        # distinguish advisory from cryptographically-bound decisions on this flag.
        "self_asserted": True,
    }
    if change_author:
        row_extra["change_author"] = change_author
    return {
        "ok": True, "impact": out, "policy": pol, "author": author,
        "self_asserted": True,
        "quorum": {"required": required, "confirmed": len(confirmed), "status": quorum_status,
                   "closed": quorum_status == "APPROVED",   # 200 != closed; check this flag
                   "approvers": confirmed, "change_id": cid},
        "sig": imp.signature, "change_id": cid, "target_fqns": fqns,
        "blast_set": imp.affected_ids, "row_extra": row_extra,
    }
