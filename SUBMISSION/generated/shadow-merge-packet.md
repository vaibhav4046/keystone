# Keystone - Shadow Merge Firewall decision packet

**Verdict: ALLOW**  (Git text conflict: NONE | Orbit collision: none)

## Executive summary
`MR-301` and `MR-302` touch different files and their Orbit blast radii do not overlap. No hidden relationship conflict - safe to merge in any order.

## The two changes
- **MR-301** changes `clear_transcript()` in `core/orbit_cli.py` (Orbit blast radius: 3 dependents)
- **MR-302** changes `precedent()` in `core/audit.py` (Orbit blast radius: 4 dependents)

## Git result: NONE
Git's merge-conflict detection is textual: it only flags overlapping line edits. These MRs edit different files, so Git is blind to the relationship between them.

## Orbit evidence (the relationship Git cannot see)
- No blast-radius overlap detected.

## CI result: exit 0 (passes)
## Reproduce
```
python skills/keystone/run_review.py shadow-merge --safe
```

## Paste-ready GitLab MR comment
```markdown
### Keystone Shadow Merge Firewall: ALLOW
MR-301 (`clear_transcript`, core/orbit_cli.py) and MR-302 (`precedent`, core/audit.py) have **no Git text conflict** and **no Orbit blast-radius overlap** - safe to merge.
```

## Honest limitations
- Computed from a committed real `orbit index` of this repo (deterministic snapshot), not a live MR webhook. Every figure is reproducible with the command above; no model is on this path.

_Git sees files. Orbit sees relationships. Keystone turns relationships into a merge gate._
