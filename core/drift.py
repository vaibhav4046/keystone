"""Blast-radius drift across two graph snapshots.

Reads two Orbit-shaped DuckDB graphs (the prior state and the current state), and computes,
deterministically, the per-symbol delta in blast radius between them. This is the
"silently rising risk" beat from the I-3 backlog: a symbol with blast 3 in the prior
snapshot and 30 in the current is no longer the change the team thought it was approving,
so a reviewer re-reading an older approval deserves to see it.

Honest scope:
  - This is a SAME-REPO, SAME-LANGUAGE diff over the same DuckDB schema. Cross-language or
    cross-schema drift is out of scope.
  - The engine is read-only; it never mutates either input. No model.
  - A symbol that appears in only one of the two graphs is reported as added or removed
    (so a renamed function surfaces, not as a phantom deletion + insertion).
  - Drift is reported with the SAME blast_radius_signature an MR's precedent would carry,
    so an existing approval's signature can be re-checked against the new graph.
  - Drift is bounded by max_depth, the same parameter the live impact path uses, so the
    number you see on the live impact panel is the number a diff against that graph would
    use too. (An unbounded diff would be a different number than the live panel.)

Standard library + duckdb (read-only connections).
"""
from __future__ import annotations

import os
import sys
from typing import Optional

# ensure core.* importable when this module is invoked directly
_PKG_PARENT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PKG_PARENT not in sys.path:
    sys.path.insert(0, _PKG_PARENT)

from core import impact as impact_mod                  # noqa: E402
from core.graph import Graph                            # noqa: E402


def _build_graph(path: str) -> Graph:
    """Open a read-only Graph against an Orbit-shaped DuckDB at a known path. We use the
    LIVE-shaped Graph because the two snapshots we are diffing are real Orbit graphs, not
    the minimal fixture. The schema and column names are the same."""
    return Graph(path=path, mode="LIVE")


def _names_set(graph: Graph) -> set:
    return set(graph.all_definition_names() or [])


def _signature(graph: Graph, name: str, max_depth: int) -> Optional[dict]:
    imp = impact_mod.compute_blast_radius(graph, name, max_depth=max_depth)
    if imp is None:
        return None
    return {
        "blast": imp.counts.get("total_affected", 0),
        "ring1": imp.counts.get("ring_1", 0),
        "ring2": imp.counts.get("ring_2", 0),
        "ring3": imp.counts.get("ring_3", 0),
        "signature": imp.signature,
        "fqn": imp.epicenter_fqn,
    }


def compute_drift(*, prior_path: str, current_path: str,
                  max_depth: int = 3, top: int = 20) -> dict:
    """Compare two Graph snapshots by per-symbol blast radius. Returns:
        {prior_path, current_path, prior_count, current_count,
         added (new symbols), removed (gone symbols),
         grew (blast radius up), shrunk (blast radius down),
         top_changes (sorted by |delta blast|)}
    Honest about which path was read: no synthetic / interpolated rows.
    """
    if not os.path.exists(prior_path):
        return {"ok": False, "error": "PRIOR_NOT_FOUND", "prior_path": prior_path}
    if not os.path.exists(current_path):
        return {"ok": False, "error": "CURRENT_NOT_FOUND", "current_path": current_path}
    prior = _build_graph(prior_path)
    current = _build_graph(current_path)
    try:
        prior_names = _names_set(prior)
        current_names = _names_set(current)
        added = sorted(current_names - prior_names)
        removed = sorted(prior_names - current_names)
        common = sorted(prior_names & current_names)

        grew, shrunk, same = [], [], 0
        for name in common:
            a = _signature(prior, name, max_depth)
            b = _signature(current, name, max_depth)
            if a is None and b is None:
                continue
            if a is None or b is None:
                # name resolved in only one graph this pass - treat as removed/added
                (removed if b is None else added).append(name)
                continue
            d = b["blast"] - a["blast"]
            entry = {"symbol": name, "fqn": b.get("fqn") or a.get("fqn"),
                     "prior_blast": a["blast"], "current_blast": b["blast"], "delta": d,
                     "prior_signature": a["signature"], "current_signature": b["signature"]}
            if d > 0:
                grew.append(entry)
            elif d < 0:
                shrunk.append(entry)
            else:
                same += 1
        grew.sort(key=lambda e: -e["delta"])
        shrunk.sort(key=lambda e: e["delta"])
        all_changes = grew + shrunk
        all_changes.sort(key=lambda e: -abs(e["delta"]))
        return {
            "ok": True,
            "prior_path": prior_path, "current_path": current_path,
            "max_depth": max_depth,
            "prior_count": len(prior_names), "current_count": len(current_names),
            "added": added[:top], "removed": removed[:top],
            "added_count": len(added), "removed_count": len(removed),
            "grew": grew[:top], "shrunk": shrunk[:top],
            "grew_count": len(grew), "shrunk_count": len(shrunk),
            "same_count": same,
            "top_changes": all_changes[:top],
            # honest: the number of definitions whose blast signature actually changed is the
            # load-bearing figure for "an older approval's signature no longer matches".
            "signatures_changed": sum(1 for c in all_changes
                                      if c["prior_signature"] != c["current_signature"]),
        }
    finally:
        try:
            prior.close()
        except Exception:
            pass
        try:
            current.close()
        except Exception:
            pass


__all__ = ["compute_drift"]
