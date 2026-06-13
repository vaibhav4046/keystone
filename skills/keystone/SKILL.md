---
name: keystone
description: Governed change review on the GitLab Orbit code knowledge graph. Given a symbol that is about to change, it uses Orbit Local to fetch the dependency graph, computes the deterministic blast radius (direct callers, transitive dependents, owning files), surfaces prior governance decisions and any contradicting rejection, and records the human decision into a tamper-evident sha256 hash-chained audit ledger. Use this skill to review a code change before merge, to answer who-approved-what-and-why, or to gate an AI-agent-proposed change through the same human-auditable workflow as a human.
metadata:
  slash-command: enabled
---

# Keystone governed change review

You are running the Keystone governed-review workflow. You do not chat about a
change; you perform a specific, auditable workflow over real graph data and stop
at a human decision. Every number you report is computed by the Keystone engine
from the GitLab Orbit Local graph; you never invent or estimate a figure.

## When to use
A developer or an AI agent is about to change a symbol (a function or class) and
needs the blast radius, the relevant precedent, and a recorded, tamper-evident
decision before merge.

## How Orbit is used
The Keystone engine reads the GitLab Orbit Local code knowledge graph. At runtime
it drives Orbit's own CLI for live schema introspection and at least one live
query (`glab orbit local schema` and `glab orbit local sql "<query>"`), and uses
the indexed DuckDB at `~/.orbit/graph.duckdb` for fast traversal. If no live
graph is present it falls back to a committed sample fixture and labels the
source FALLBACK. You never present fixture data as live.

## The workflow you automate
1. Resolve the target symbol against the graph. If it does not exist, say so and stop.
2. Call the Keystone impact endpoint to get the deterministic blast radius:
   `GET /api/impact/{symbol}` returns the epicenter, the severity rings
   (ring 1 direct callers, ring 2+ transitive dependents), the affected count,
   the owning files and directories, and a stable blast-radius signature hash.
3. Call the precedent endpoint to surface prior governance:
   `GET /api/precedent/{symbol}` returns how many times this symbol or this exact
   blast signature was approved or rejected before, the verbatim most recent
   rationale, and a contradiction flag when a prior REJECTION matches. If a
   contradiction exists, state it plainly and prominently. You inform; you never
   auto-decide.
4. Present the governed-review report: the affected count and rings, the owners,
   the precedent counts, and any contradiction, every fact traceable to the graph
   or to a specific ledger row hash.
5. Require an explicit human decision with a reviewer name and a written reason.
   Record it: `POST /api/approve` with {name, decision: approve|reject, reviewer,
   rationale}. This appends one sha256 hash-linked row to the audit ledger.
6. Confirm the chain still verifies: `GET /api/audit/verify` returns ok plus the
   first broken index if any. Report verified or broken; never assert it without
   the recompute.

## Hard rules
You never fabricate a count; the engine computes every figure. You never
recommend or pre-select the verdict; precedent informs, the human decides. You
never claim the chain is verified without the live recompute. You never present
the fallback fixture as the live Orbit graph.

## Reference workflow runner
`skills/keystone/run_review.py` performs this exact workflow end to end against
the Keystone API and is the runnable proof that the skill automates an action
rather than chatting. Invoke it as `python skills/keystone/run_review.py <symbol>`
to produce the report, or with `--decide approve|reject --reviewer NAME
--reason TEXT` to record the governed decision.
