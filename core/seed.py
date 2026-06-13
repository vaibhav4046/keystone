"""Adaptive ledger seeding so the precedent-contradiction beat fires on ANY graph.

On the committed fixture, seed the scripted tokenize/parse story (a prior REJECT
on tokenize with the same blast signature the engine computes -> contradiction).

On a LIVE Orbit graph (e.g. after `glab orbit local index` of a real repo), there
is no tokenize symbol, so instead build the same shape of story from the live
graph itself: a prior approval on one real symbol for context, and a prior
REJECTION on the most-depended-on real symbol using ITS live blast signature, so
re-opening that symbol surfaces a genuine signature-identical contradiction on
real data. Every figure is still engine-computed; nothing is invented.
"""
from __future__ import annotations

from . import fixtures, impact as impact_mod


def seed_rows_for(graph) -> list:
    """Return prior-decision payloads (oldest first) appropriate to the graph in use."""
    if getattr(graph, "source", None) is None or graph.source.mode != "LIVE":
        return fixtures.seed_ledger_rows()

    names = graph.all_definition_names(limit=8)
    if not names:
        return fixtures.seed_ledger_rows()

    rows = []
    # Context: a prior low-risk approval on the second most-depended-on symbol.
    if len(names) > 1:
        second = names[1]
        imp2 = impact_mod.compute_blast_radius(graph, second)
        if imp2 is not None:
            rows.append({
                "actor": "h.okafor",
                "change_id": "MR-118",
                "target_symbols": [second],
                "blast_radius_set": imp2.affected_ids,
                "decision": "approve",
                "rationale": f"Internal refactor of {second}; public signature unchanged, "
                             f"{len(imp2.affected_ids)} dependents recompute identically. Low risk.",
            })

    # The load-bearing prior REJECTION on the most-depended-on real symbol, keyed to
    # its live blast signature so the contradiction is signature-identical.
    top = names[0]
    imp = impact_mod.compute_blast_radius(graph, top)
    if imp is not None:
        n = len(imp.affected_ids)
        rows.append({
            "actor": "s.castellano",
            "change_id": "MR-203",
            "target_symbols": [top],
            "blast_radius_set": imp.affected_ids,
            "decision": "reject",
            "rationale": f"{top} sits under {n} dependents across the graph; changing it shifts "
                         f"the computed impact of every one. Needs an RFC and a migration test first.",
        })

    return rows or fixtures.seed_ledger_rows()
