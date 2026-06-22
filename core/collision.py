"""Cross-MR blast-collision detection: the hazard Git and GitLab are blind to.

Git's merge-conflict detection is TEXTUAL: two merge requests collide only if they edit
overlapping lines. But two MRs can be semantically entangled while touching entirely
different files - MR A changes a function that MR B's change depends on. There is no text
conflict, both pass review independently, and merging them in the wrong order (or at all)
silently breaks something neither reviewer could see. This is a real, recurring incident
class ("our two changes were fine alone and broke together"), and nothing in the standard
review surface shows it.

Keystone can, because Orbit gives it the call graph. This module computes, for a set of
OPEN merge requests, where their blast radii COLLIDE on the graph, classifies each
collision by how dangerous it is, ranks the MRs by collision risk, and proposes a safe
merge order (a topological order of "A changes what B depends on" edges; a cycle means
"these cannot be safely ordered - coordinate"). Every figure is deterministic graph
computation. No model.

Collision kinds, strongest first:
  - same_change : both MRs change the SAME symbol (A.touched ∩ B.touched).
  - change_in_blast : one MR CHANGES a symbol that is inside the OTHER MR's blast radius
                      (A.touched ∩ B.affected) - the directional, most insidious case.
  - blast_overlap : their blast radii share dependents (A.affected ∩ B.affected) - both
                    perturb code that leans on the same things.
"""
from __future__ import annotations

from typing import Optional

from . import impact as impact_mod

_KIND_WEIGHT = {"same_change": 5, "change_in_blast": 3, "blast_overlap": 1}


def _footprint(graph, symbols, max_depth: int) -> dict:
    """The region of the graph an MR perturbs: the symbols it CHANGES (touched epicenters)
    and everything in their blast radius (affected dependents), plus a fan-in weight per
    node so a collision on a heavily-depended-on symbol counts for more."""
    touched, affected, names, fanin = set(), set(), {}, {}
    for s in symbols:
        imp = impact_mod.compute_blast_radius(graph, s, max_depth=max_depth)
        if imp is None:
            continue
        touched.add(imp.epicenter_id)
        names[imp.epicenter_id] = imp.epicenter_name
        for i in imp.affected_ids:
            affected.add(i)
            names[i] = imp.names.get(i, str(i))
        # weight = blast size of the touched symbol (its own consequence in the graph)
        fanin[imp.epicenter_id] = max(fanin.get(imp.epicenter_id, 0), len(imp.affected_ids))
    return {"touched": touched, "affected": affected, "region": touched | affected,
            "names": names, "weight": fanin}


def _classify(a: dict, b: dict) -> dict:
    """The collision between two MR footprints: the shared ids by kind + a severity score."""
    same = a["touched"] & b["touched"]
    cross = (a["touched"] & b["affected"]) | (b["touched"] & a["affected"])
    cross -= same
    blast = (a["affected"] & b["affected"]) - same - cross
    if not (same or cross or blast):
        return {}
    names = {**a["names"], **b["names"]}

    def label(ids):
        return sorted({names.get(i, str(i)) for i in ids})
    # severity: weighted by kind and by how depended-on the shared nodes are
    weight = {**a["weight"], **b["weight"]}
    sev = 0
    for ids, kind in ((same, "same_change"), (cross, "change_in_blast"), (blast, "blast_overlap")):
        for i in ids:
            sev += _KIND_WEIGHT[kind] * (1 + weight.get(i, 0))
    kind = "same_change" if same else ("change_in_blast" if cross else "blast_overlap")
    return {"kind": kind, "severity": sev,
            "same_change": label(same), "change_in_blast": label(cross),
            "blast_overlap": label(blast),
            # the shared DEPENDENTS must exclude the two changed symbols themselves
            "shared": label((same | cross | blast) - a["touched"] - b["touched"])}


def find_top_collision(graph, top_k: int = 25, max_depth: int = 3) -> Optional[dict]:
    """Find the worst GENUINELY-INDEPENDENT collision among the repo's TOP-K most-consequential
    symbols: a pair where NEITHER symbol sits in the other's blast radius - so two parallel MRs
    changing them have no Git conflict and neither review sees the other - yet they SHARE the most
    runtime dependents. The textbook "both pass review, break together" hazard, with an honest count
    that excludes the two changed symbols themselves. Deterministic, from the repo's own call graph.

    "Worst" is scoped to the candidate window, NOT the global maximum: top_k bounds how many of the
    highest-fan-in symbols are paired (default 25, floored at 4 so a tiny top_k never silently yields
    an empty scan). A larger top_k can surface a larger collision among less-central symbols (on
    pallets/click, top_k=25 gives 64 shared dependents and top_k=60 gives 71), so the headline is
    honestly "the worst among the K most-consequential symbols" - the deliberate, stable framing the
    docs and tests pin. Returns {a, b, shared, shared_count, kind='blast_overlap', severity, blast_a,
    blast_b} or None."""
    names = graph.all_definition_names(limit=max(top_k, 4))
    fps = {}
    for n in names:
        fp = _footprint(graph, [n], max_depth)
        if fp["affected"]:                       # only symbols with dependents can collide
            fps[n] = fp
    cand = list(fps.items())
    best, best_key = None, (-1, -1)
    for i in range(len(cand)):
        for j in range(i + 1, len(cand)):
            na, fa = cand[i]
            nb, fb = cand[j]
            # genuine independence: neither symbol is in the other's blast radius (no call edge between them),
            # which is exactly what makes the two MRs look conflict-free to Git and to each reviewer.
            if (fa["touched"] & fb["affected"]) or (fb["touched"] & fa["affected"]):
                continue
            shared = (fa["affected"] & fb["affected"]) - fa["touched"] - fb["touched"]
            if not shared:
                continue
            names_map = {**fa["names"], **fb["names"]}
            # report distinct dependent NAMES, excluding the two changed symbols themselves (a repo can
            # hold several same-named defs, so exclude by name too, not just by the chosen epicenter ids).
            shared_names = sorted({names_map.get(x, str(x)) for x in shared} - {na, nb})
            if not shared_names:
                continue
            weight = {**fa["weight"], **fb["weight"]}
            # severity is a finer id-level weight (per shared id, fan-in-weighted), used ONLY as a
            # secondary tiebreak after the name-deduped shared_count; it can exceed shared_count when
            # several dependents share a short name. shared_count stays the reported headline.
            sev = sum(1 + weight.get(x, 0) for x in shared)
            key = (len(shared_names), sev)       # most shared dependents, then most depended-on
            if key > best_key:
                best_key = key
                best = {"a": na, "b": nb, "shared": shared_names,
                        "shared_count": len(shared_names), "kind": "blast_overlap", "severity": sev,
                        "blast_a": len(fa["affected"]), "blast_b": len(fb["affected"])}
    return best


def _directional_edges(mrs_fp: list) -> list:
    """Edges A -> B meaning 'A changes a symbol that B's change DEPENDS ON', so A should
    merge first and B re-review against it.

    B depends on A's change when one of B's touched symbols sits inside A's blast radius
    (A's affected set = everything that depends on what A changed). So the edge condition is
    A.affected ∩ B.touched, NOT A.touched ∩ B.affected (that would invert the order and tell
    you to merge the dependent before the thing it relies on)."""
    edges = []
    for ia, (ida, fa) in enumerate(mrs_fp):
        for ib, (idb, fb) in enumerate(mrs_fp):
            if ia == ib:
                continue
            if fa["affected"] & fb["touched"]:        # B changes something inside A's blast -> A first
                edges.append((ida, idb))
    return edges


def _merge_order(ids: list, edges: list):
    """Kahn topological sort over the directional edges. Returns (order, cycle_members).
    A cycle means the MRs cannot be safely ordered and must be coordinated."""
    succ = {i: set() for i in ids}
    indeg = {i: 0 for i in ids}
    for a, b in edges:
        if b not in succ[a]:               # dedup: only the first A->B edge raises the in-degree
            succ[a].add(b); indeg[b] += 1
    order, ready = [], sorted([i for i in ids if indeg[i] == 0])
    while ready:
        n = ready.pop(0)
        order.append(n)
        for m in sorted(succ[n]):
            indeg[m] -= 1
            if indeg[m] == 0:
                ready.append(m)
        ready.sort()
    cycle = sorted([i for i in ids if i not in order])
    return order, cycle


def detect_collisions(graph, mrs: list, max_depth: int = 3) -> Optional[dict]:
    """Find blast-radius collisions across a set of open MRs.

    mrs: [{"id": str, "symbols": [str, ...]}]. Returns the pairwise collisions (by kind +
    severity + the shared symbols), a per-MR risk roll-up, and a suggested safe merge order
    (or the cycle that makes one impossible). Returns None if fewer than one MR resolves."""
    fps = []
    seen_ids = {}
    for mr in mrs:
        mid = str(mr.get("id") or f"MR-{len(fps) + 1}")
        # Duplicate MR ids would collapse the merge-order graph (succ/indeg are keyed by id), so
        # uniquify them - two distinct MRs that happen to share an id stay distinct in the sort.
        if mid in seen_ids:
            seen_ids[mid] += 1
            mid = f"{mid}#{seen_ids[mid]}"
        else:
            seen_ids[mid] = 1
        syms = [s for s in (mr.get("symbols") or []) if s]
        fp = _footprint(graph, syms, max_depth)
        if fp["region"]:
            fps.append((mid, fp, syms))
    if not fps:
        return None

    collisions = []
    for i in range(len(fps)):
        for j in range(i + 1, len(fps)):
            ida, fa, _ = fps[i]
            idb, fb, _ = fps[j]
            c = _classify(fa, fb)
            if c:
                collisions.append({"mr_a": ida, "mr_b": idb, **c})
    collisions.sort(key=lambda c: (-c["severity"], c["mr_a"], c["mr_b"]))

    # per-MR risk roll-up
    per_mr = []
    for mid, fp, syms in fps:
        cs = [c for c in collisions if mid in (c["mr_a"], c["mr_b"])]
        per_mr.append({
            "id": mid, "symbols": syms,
            "changes": sorted({fp["names"].get(i, str(i)) for i in fp["touched"]}),
            "blast_size": len(fp["affected"]),
            "collides_with": sorted({(c["mr_b"] if c["mr_a"] == mid else c["mr_a"]) for c in cs}),
            "risk": sum(c["severity"] for c in cs),
        })
    per_mr.sort(key=lambda m: (-m["risk"], m["id"]))

    ids = [mid for mid, _, _ in fps]
    edges = _directional_edges([(mid, fp) for mid, fp, _ in fps])
    order, cycle = _merge_order(ids, edges)

    n_coll = len(collisions)
    if cycle:
        verdict = f"{len(cycle)} MRs form a dependency cycle and cannot be safely ordered - coordinate them."
    elif n_coll == 0:
        verdict = "No blast-radius collisions - these MRs are independent and any merge order is safe."
    else:
        verdict = (f"{n_coll} collision(s) across {len(ids)} MRs. Suggested safe merge order avoids "
                   f"merging a dependent before the change it relies on.")

    return {
        "mrs": ids,
        "collisions": collisions,
        "per_mr": per_mr,
        "merge_order": order,
        "uncoordinable_cycle": cycle,
        "counts": {"mrs": len(ids), "collisions": n_coll,
                   "colliding_mrs": len({m["id"] for m in per_mr if m["collides_with"]})},
        "verdict": verdict,
    }
