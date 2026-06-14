"""Merge-request blast radius: the UNION across every symbol a change touches.

A real merge request edits several definitions, not one. Keystone's per-symbol impact
is correct but narrow; this composes it into the MR-level view the README flagged as the
remaining API-model gap. It computes, deterministically and with no model:

  - the UNION of collateral dependents across all touched symbols (each touched symbol is
    a change, not collateral, so the touched set is excluded from "affected"),
  - the STRICTEST governance outcome - because the union's affected-file count is at least
    as large as any single symbol's, evaluating policy on the union yields a tier no weaker
    than any symbol's, which is exactly the conservative MR rule,
  - a per-symbol breakdown so a reviewer still sees which change drives the tier,
  - an MR signature bound to the SET of touched epicenters plus the union, so two MRs that
    touch the same symbols with the same blast still match for precedent.

Every figure comes from core/impact.py over real graph rows. Standard library only.
"""
from __future__ import annotations

import hashlib
import json
from typing import Optional

from . import impact as impact_mod, policy as policy_mod, attest as attest_mod


def mr_signature(epicenter_ids, affected_ids) -> str:
    """Stable sha256 over the SORTED set of touched epicenters plus the sorted union of
    affected ids. Binding the epicenter set (not a single id) is what makes this an MR-level
    identity rather than a single-symbol one."""
    payload = json.dumps(
        {"epicenters": sorted(set(int(x) for x in epicenter_ids)),
         "affected": sorted(set(int(x) for x in affected_ids))},
        separators=(",", ":"), sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


_ACTION_RANK = {"ALLOW": 0, "HOLD": 1, "BLOCK": 2}


def compute_mr_impact(graph, target_names, max_depth: int = 3) -> Optional[dict]:
    """Compose per-symbol impacts into one MR-level impact + the strictest policy outcome.
    Returns None if none of the names resolve. The returned dict mirrors the single-symbol
    shape closely enough that policy.evaluate and attest consume it unchanged.

    Conservatism guarantee (the whole point of an MR gate): the union outcome is NEVER
    weaker than any constituent symbol's. This is enforced two ways, belt and suspenders:
      1. the union COLLATERAL is the union of each symbol's full affected set (each already
         excludes only its OWN epicenter), so the union's affected files/defs are a true
         superset of every single symbol's -> a monotonic policy yields a tier >= each; and
      2. an explicit FLOOR clamps the union tier / action / approver count up to the
         strictest single-symbol value, so even a non-monotonic custom policy cannot relax
         the gate by adding a touched symbol. (A prior version subtracted touched epicenters
         from the count, which could DROP a sole-def file and weaken the union - fixed.)"""
    seen, names_in = set(), []
    for n in target_names:                       # dedup, preserve order
        if n not in seen:
            seen.add(n); names_in.append(n)

    impacts = []
    for n in names_in:
        imp = impact_mod.compute_blast_radius(graph, n, max_depth=max_depth)
        if imp is not None:
            impacts.append((n, imp))
    if not impacts:
        return None

    policy = policy_mod.load_policy()
    tier_rank = {t["name"]: i for i, t in enumerate(policy["tiers"])}
    tier_by_name = {t["name"]: t for t in policy["tiers"]}

    epi_ids = sorted({imp.epicenter_id for _, imp in impacts})

    # per-symbol policy: both the reviewer breakdown AND the conservative floor.
    per_symbol = []
    for n, imp in impacts:
        d = imp.to_dict()
        p = policy_mod.evaluate(d, {})
        per_symbol.append({
            "symbol": n, "epicenter": d["epicenter"].get("fqn") or d["epicenter"].get("name"),
            "tier": p["tier"], "action": p["action"],
            "total_affected": d["counts"].get("total_affected", 0),
            "required_approvers": p["required_approvers"], "signature": d["signature"],
        })

    # UNION collateral = union of each symbol's affected ids. Each per-symbol affected set
    # already excludes ONLY that symbol's own epicenter, so a touched symbol B that is a
    # dependent of touched symbol A stays counted (it is genuine collateral of A). This makes
    # the union affected set a superset of every single symbol's -> conservative by construction.
    union_def_ids = sorted(set().union(*[set(imp.affected_ids) for _, imp in impacts]))
    names, ring_of = {}, {}
    for _, imp in impacts:
        names.update(imp.names)
        rd = {o["id"]: o.get("ring", 1) for o in imp.owners}
        for i in imp.affected_ids:
            r = rd.get(i, 1) or 1
            ring_of[i] = min(ring_of.get(i, r), r)
    owners = [{"id": i, "ring": max(1, ring_of.get(i, 1)), **graph.owning_file_and_dir(i)}
              for i in union_def_ids]

    sig = mr_signature(epi_ids, union_def_ids)
    impact_dict = {
        "epicenter": {"id": None, "name": f"MR · {len(impacts)} symbol(s)",
                      "fqn": ", ".join(n for n, _ in impacts), "file": ""},
        "affected_ids": union_def_ids,
        "counts": {"total_affected": len(union_def_ids)},
        "signature": sig,
        "owners": owners,
        "names": {str(k): names.get(k, str(k)) for k in union_def_ids},
    }
    pol = policy_mod.evaluate(impact_dict, {})

    # FLOOR clamp: never weaker than the strictest constituent symbol.
    floor_tier = max((s["tier"] for s in per_symbol), key=lambda t: tier_rank.get(t, 0))
    union_tier = pol["tier"] if tier_rank.get(pol["tier"], 0) >= tier_rank.get(floor_tier, 0) else floor_tier
    union_approvers = max([pol["required_approvers"], tier_by_name[union_tier]["required_approvers"]]
                          + [s["required_approvers"] for s in per_symbol])
    floor_action = max((s["action"] for s in per_symbol), key=lambda a: _ACTION_RANK.get(a, 0))
    union_action = pol["action"] if _ACTION_RANK.get(pol["action"], 0) >= _ACTION_RANK.get(floor_action, 0) else floor_action
    clamped = (union_tier != pol["tier"]) or (union_action != pol["action"]) or (union_approvers != pol["required_approvers"])
    reasons = list(pol["reasons"])
    if clamped:
        reasons.append(f"floor: not weaker than the strictest touched symbol -> {union_tier} / "
                       f"{union_action} / {union_approvers} approver(s)")

    impact_dict["policy"] = pol
    impact_dict["orbit_snapshot_sha256"] = attest_mod.orbit_snapshot_sha256(impact_dict)

    # the symbol that drives the MR tier: by policy tier rank, then approvers, then def count
    strictest = max(per_symbol, key=lambda s: (tier_rank.get(s["tier"], 0),
                                               s["required_approvers"], s["total_affected"]))["symbol"]

    return {
        "symbols": names_in,
        "resolved": [n for n, _ in impacts],
        "unresolved": [n for n in names_in if n not in {x for x, _ in impacts}],
        "union": {
            "tier": union_tier, "action": union_action,
            "required_approvers": union_approvers,
            "counts": pol["counts"], "reasons": reasons,
            "signature": sig, "orbit_snapshot_sha256": impact_dict["orbit_snapshot_sha256"],
            "policy_version": pol["policy_version"], "policy_hash": pol["policy_hash"],
        },
        "strictest_symbol": strictest,
        "per_symbol": per_symbol,
    }
