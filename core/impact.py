"""Deterministic blast-radius and severity ranking over the graph.

Every figure here is computed from real graph rows by bounded graph traversal.
No model, no estimate, no randomness. Same input graph always yields the same
rings, counts, and signature hash. These are the numbers the UI displays.

Algorithms (named in master-prompt Section P):
  1. reverse-edge caller traversal      -> ring 1 (direct dependents)
  2. bounded transitive closure (BFS)   -> rings 2..max_depth (downstream dependents)
  3. blast_radius_signature_hash        -> stable sha256 over the sorted affected id set

Edge meaning: (src -> dst, 'calls') = src calls dst, so dependents of a target T
are found by walking edges in REVERSE (who calls T, then who calls them).
"""
from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

DEFAULT_MAX_DEPTH = 3


@dataclass
class Impact:
    epicenter_id: int
    epicenter_name: str
    rings: dict              # hop-distance -> sorted list of def ids
    affected_ids: list       # all dependents, sorted, excludes the epicenter
    counts: dict             # {"ring_1": n, "ring_2": n, ..., "total_affected": n, "unaffected": n}
    signature: str           # blast_radius_signature_hash
    owners: list             # [{"id","ring","name","file","dir"}] for epicenter + each affected def
    names: dict              # {def_id: name} for epicenter + every affected def

    def to_dict(self) -> dict:
        return {
            "epicenter": {"id": self.epicenter_id, "name": self.epicenter_name},
            "rings": {str(k): v for k, v in self.rings.items()},
            "affected_ids": self.affected_ids,
            "counts": self.counts,
            "signature": self.signature,
            "owners": self.owners,
            "names": {str(k): v for k, v in self.names.items()},
        }


def blast_radius_signature(affected_ids) -> str:
    """Stable sha256 over the sorted, de-duplicated affected definition id set.
    Two changes with the same dependent set share a signature, which is what the
    Precedent Panel matches on."""
    ordered = sorted(set(int(x) for x in affected_ids))
    payload = json.dumps(ordered, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_blast_radius(graph, target_name: str, max_depth: int = DEFAULT_MAX_DEPTH) -> Optional[Impact]:
    epi = graph.find_definition(target_name)
    if epi is None:
        return None
    epi_id = epi["id"]

    # Bounded reverse-BFS: ring distance from the epicenter along reverse 'calls' edges.
    ring_of = {epi_id: 0}
    rings = {0: [epi_id]}
    q = deque([(epi_id, 0)])
    while q:
        node, dist = q.popleft()
        if dist >= max_depth:
            continue
        for caller in graph.direct_callers(node):
            if caller not in ring_of:
                ring_of[caller] = dist + 1
                rings.setdefault(dist + 1, []).append(caller)
                q.append((caller, dist + 1))

    for d in rings:
        rings[d] = sorted(rings[d])
    affected = sorted([i for i in ring_of if i != epi_id])

    counts = {}
    for d in sorted(rings):
        if d == 0:
            continue
        counts[f"ring_{d}"] = len(rings[d])
    counts["total_affected"] = len(affected)
    counts["unaffected"] = max(0, graph.total_definitions() - 1 - len(affected))

    owners = [{"id": epi_id, "ring": 0, **graph.owning_file_and_dir(epi_id)}]
    names = {epi_id: epi["name"]}
    for i in affected:
        owners.append({"id": i, "ring": ring_of[i], **graph.owning_file_and_dir(i)})
        names[i] = graph.name_of(i)

    return Impact(
        epicenter_id=epi_id,
        epicenter_name=epi["name"],
        rings=rings,
        affected_ids=affected,
        counts=counts,
        signature=blast_radius_signature(affected),
        owners=owners,
        names=names,
    )
