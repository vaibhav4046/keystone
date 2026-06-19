## Keystone Harness: BLOCK

This MR (`MR-204`) changes 1 symbol(s) (agent: `copilot-workspace`).

| Symbol | Tier | Blast | Verdict |
|--------|------|-------|---------|
| `compute_blast_radius` | CROSS_TEAM | 12 defs | **BLOCK** |

**Cross-MR collisions:** 2 found. Safe merge order: MR-204 -> MR-207 -> MR-211

**Why Keystone blocked:**

- `compute_blast_radius`: 12 dependent definitions across 5 files / 3 directories -> tier CROSS_TEAM
- `compute_blast_radius`: BLOCK: identical blast radius was rejected before (MR-203 by s.castellano)
- `compute_blast_radius`: Agent-authored change (agent=copilot-workspace) on BLOCK tier requires human reviewer confirmation

**Required action:** Resolve the precedent or obtain owner approval before merging.

---
_Keystone Engineering Harness. Engine computed from the Orbit graph. Same graph + same policy = same decision._
