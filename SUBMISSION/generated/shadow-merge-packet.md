# Keystone - Shadow Merge Firewall decision packet

**Verdict: HOLD**  (Git text conflict: NONE | Orbit collision: DETECTED)

## Executive summary
`MR-204` and `MR-211` touch different files, so Git reports no conflict and both pass review independently. On the GitLab Orbit graph their blast radii collide on a shared dependency, so merging both can break code neither reviewer changed.

## The two changes
- **MR-204** changes `compute_blast_radius()` in `core/impact.py` (Orbit blast radius: 12 dependents)
- **MR-211** changes `append()` in `core/audit.py` (Orbit blast radius: 17 dependents)

## Git result: NONE
Git's merge-conflict detection is textual: it only flags overlapping line edits. These MRs edit different files, so Git is blind to the relationship between them.

## Orbit evidence (the relationship Git cannot see)
- Collision kind: `blast_overlap`
- Shared dependents (5): approve, get_json, main, post_json, precedent
- These definitions transitively depend on BOTH changed symbols, so a change to either ripples into them; changing both at once compounds the risk with no text conflict to warn you.

## Recommended developer action
Do not merge both blindly. Stack the two MRs into one coordinated review, add an integration test exercising the shared dependents, and merge in the order Keystone's safe-merge-order computes.

## CI result: exit 2 (fails the pipeline)
## Reproduce
```
python skills/keystone/run_review.py shadow-merge
```

## Paste-ready GitLab MR comment
```markdown
### Keystone Shadow Merge Firewall: HOLD
MR-204 (`compute_blast_radius`, core/impact.py) and MR-211 (`append`, core/audit.py) have **no Git text conflict** but **collide on the Orbit graph** via 5 shared dependents (approve, get_json, main, post_json, precedent). Coordinate these before merge.
```

## Honest limitations
- Computed from a committed real `orbit index` of this repo (deterministic snapshot), not a live MR webhook. Every figure is reproducible with the command above; no model is on this path.

_Git sees files. Orbit sees relationships. Keystone turns relationships into a merge gate._
