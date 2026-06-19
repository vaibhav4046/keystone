# Keystone Engineering Harness Report

**Mode:** sample
**Overall Verdict:** BLOCK
**Agent:** copilot-workspace (bot)
**MR:** MR-204
**Symbols touched:** compute_blast_radius

## Pipeline Stages

| Stage | Status | Detail |
|-------|--------|--------|
| SYMBOL_RESOLVE | done (456ms) | total: 1; found: 1; missing: none |
| BLAST_COMPUTE | done (14ms) | symbols_evaluated: 1 |
| POLICY_GATE | done (0ms) | blocked: 1; held: 0; allowed: 0 |
| COLLISION_SCAN | done (36ms) | collisions: 2; colliding_mrs: 3 |
| VERDICT | done (0ms) | overall: BLOCK; blocked: compute_blast_radius; held: none |

## Per-Symbol Verdicts

### `compute_blast_radius` - **BLOCK**

- Ring-1 (direct dependents): **12**
- Total affected: **12**
- Policy tier: **CROSS_TEAM**
- Required approvers: **2**
- Reasons: 12 dependent definitions across 5 files / 3 directories -> tier CROSS_TEAM; BLOCK: identical blast radius was rejected before (MR-203 by s.castellano); Agent-authored change (agent=copilot-workspace) on BLOCK tier requires human reviewer confirmation

## Cross-MR Collision Analysis

- MRs analyzed: **3**
- Collisions found: **2**
- Colliding MRs: **3**

**MR-211 x MR-204** - blast_overlap (severity: 6)
  Shared symbols: approve, get_json, main, post_json, precedent

**MR-207 x MR-204** - change_in_blast (severity: 3)
  Shared symbols: impact

**Safe merge order:** MR-204 -> MR-207 -> MR-211

**Verdict:** 2 collision(s) across 3 MRs. Suggested safe merge order avoids merging a dependent before the change it relies on.

## Orbit Snapshot Attestation

Combined snapshot SHA-256: `c7ca1cb5a5207d1a...`

---
_Engine computed from the Orbit code graph. AI explains; the deterministic gate decides._
