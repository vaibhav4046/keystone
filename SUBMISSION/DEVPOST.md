# Keystone - Devpost submission text

Paste these into the Devpost fields. Written to be honest and specific. No em-dashes, no
hashtags, no invented numbers or users. Fill the two links and the video URL where marked.

GitLab repo (PRIMARY — required by the rules): https://gitlab.com/lalwanivaibhav079/keystone   (public, MIT, synced to commit 8069f64)
GitHub mirror (secondary): https://github.com/vaibhav4046/keystone
AI Catalog artifact: <PASTE CATALOG LINK — publish .gitlab/agents/keystone/agent.yml to the AI Catalog, then paste>
Live demo: https://vaibhav4046.github.io/keystone/
Video (public, under 3 min): <PASTE YOUTUBE OR VIMEO URL>

---

## Elevator pitch (one line)

Keystone turns the GitLab Orbit code graph into a deterministic engineering harness and merge safety controller for agent-authored code changes.

## Inspiration

As autonomous AI coding agents move from simple autocomplete to authoring complex, multi-file patches, they introduce a massive new safety risk. Agents propose code changes, but they have no accountability, cannot be paged at 2 AM, and do not understand the systemic consequences of their edits. skurrying human reviewers skimming a diff cannot foresee when changing a utility function in one file silently breaks a dependency in another. Git sees files; Orbit sees relationships; Keystone sees consequences.

We built Keystone to act as the missing **governance and engineering harness** around coding agents. By wrapping agent proposals in a deterministic verification pipeline driven by the Orbit code graph, we ensure no agent-authored change reaches production without safety clearances and human-in-the-loop approvals.

## What it does

Keystone turns code review from a passive dashboard into an active, deterministic merge controller:

1. **The Engineering Harness**: A 5-stage verification pipeline for agent-authored patches:
   - **Symbol Resolve**: Validates touched symbols exist in the Orbit graph.
   - **Blast Compute**: Computes the blast radius (impact depth, definitions, owners) using reverse-BFS.
   - **Policy Gate**: Maps blast impact to ALLOW, HOLD, or BLOCK policy tiers.
   - **Collision Scan**: Scans for cross-MR blast overlaps (hidden merge collisions) across open MRs.
   - **Verdict**: Decides if a change is safe to merge, suggesting a topologically sorted safe merge order.

2. **Cross-MR Blast Collisions**: Detects when two independent merge requests overlap in their call graphs (no Git conflict, but a dependency collision) and computes a safe merge sequence.

3. **Governance & Audit Trail**: Restricts autonomous agents from self-approving, enforces four-eyes rules, and commits all decisions to an HMAC-keyed, hash-chained ledger.

4. **Real AI, Off the Trust Path**: A bounded tool-using agent explains the impact and recommends reviewers, but never decides the verdict. The model proposes; the deterministic engine decides.

The command center is fully polished: a premium dark/light dashboard, a 5-step interactive merge collision simulator, and the animated 5-stage **Engineering Harness visualizer** showing live pipeline state for agent-authored changes.

## How we built it

One pure-Python engine owns every number: it reads the Orbit Local graph (the DuckDB file Orbit
itself produces), computes the bounded reverse-BFS blast radius and the blast signature, detects
the cross-MR collisions and the safe merge order, maps the policy tier, and maintains the
hash-chained ledger. A single FastAPI app serves it. The web command center, a command-line skill,
and the CI gate are thin clients of that one core.

The integration with Orbit is direct and load-bearing: the engine reads Orbit's own graph
database, and the product also drives the real `orbit` CLI (`orbit schema` and `orbit sql`) at
session start and as a live cross-check. The public demo is not a mock. It is served from a real
`orbit index` of this very repository: 262 definitions, 689 relationships, 120 verified symbols,
and for every symbol it shows the exact `orbit sql` command and the count it returned. The build
is deterministic, so continuous integration rebuilds the bundle byte-for-byte and fails on drift.

The AI runs on a free provider ladder (OpenRouter and others) behind hard timeouts, with a
deterministic fallback so the whole product works with zero API keys.

## How it uses the GitLab Duo Agent Platform and AI Catalog

The submitted artifact is a Duo Agent Platform agent defined at `.gitlab/agents/keystone/agent.yml`:
a governed-review persona with a fixed workflow (resolve symbol on the Orbit graph, compute blast
radius, surface precedent and contradictions, require a human decision, verify the ledger) and a
tool set bound to the Keystone engine endpoints. It is published to the GitLab AI Catalog so other
teams can install it.

The same workflow ships as a runnable skill that needs no server:
`python skills/keystone/run_review.py <symbol> --local` performs the full automation in-process
against the committed real Orbit index, and `--fail-on-block` makes it an enforceable CI gate that
exits non-zero on a governance BLOCK. That is the proof the agent automates an action rather than
chatting: it produces a deterministic report, a verdict, and a tamper-evident ledger row.

## How GitLab Orbit is used (specifically)

The engine reads the Orbit Local graph database directly (the DuckDB file `orbit index` produces:
`gl_definition`, `gl_edge`, `gl_file`, `gl_directory`) and drives Orbit's own CLI
(`glab orbit local schema`, `glab orbit local sql`) for live introspection and cross-check. The
blast radius is a bounded reverse-BFS over `gl_edge` CALLS rows; the cross-MR collision is the
intersection of two symbols' dependent sets. Remove the Orbit graph and there is nothing to compute.
The public demo serves a real `orbit index` of this repo (262 defs) and a second real index of
pallets/click (1,841 defs) so the hazard is shown on recognizable code, not a toy.

## Challenges we ran into

The most useful bug came from running it for real. The first version was written against a guessed
Orbit schema. The moment I indexed this repo with the real Orbit binary, every query was wrong,
because the real schema is `gl_definition`, `gl_edge`, `gl_file`, `gl_directory` with specific
columns and edge kinds. Rewriting the engine against the real schema is the reason the demo is
honest today.

The second was a governance-inverting bug in the multi-symbol merge-request union. Combining the
blast radius across several touched symbols could, in one edge case, relax the tier below what a
single symbol alone would require. A brute-force check over every pair and triple in the fixture
caught it, and the union now clamps to the strictest constituent tier as a floor. A passing test
had missed it because the fixed test input happened to dodge the case, which was its own lesson.

## Accomplishments I am proud of

The trust boundary held all the way through. Across a lot of iteration, the rule never bent: the
engine computes every number from real graph rows, and the model is never allowed to produce a
number or a verdict. That is what makes the audit trail worth anything.

And the honesty of the demo. The numbers on screen are a real Orbit index of the repo, checkable
against the Orbit command shown. The status panel always says whether the data is live, a
committed snapshot, or a fallback fixture. The identity model is labeled exactly as strong as it
is and no stronger.

## What I learned

Adversarial verification earns its cost. Every time I had a separate pass try to break a change
before committing it, it found something a passing test had missed. And the hardest part of a
governance tool is not the enforcement, it is being precise and honest about what the enforcement
does and does not guarantee.

## What's next

Three more graph-driven gates are designed and deliberately not faked, because they need Orbit
Remote data the free local graph does not contain: a dependency-depth quarantine that blocks an
agent-authored change reaching a known-vulnerable package, an ownership-entropy gate that catches
stale owners, and a pipeline-health risk multiplier. Each is one Orbit Remote query away and is
documented rather than mocked. Binding reviewer identity to a verified GitLab OIDC token on a real
pipeline, instead of the self-asserted browser demo, is the other near step, and the code path for
it already verifies the token signature offline in the test suite.

Publishing the agent to the GitLab AI Catalog is the immediate next step after the repo is
mirrored to GitLab.

## Who it is for, and who it is not for

It is for a platform or CODEOWNERS team inside a large organization on GitLab Ultimate with Orbit
turned on, reviewing merge requests at a scale where a change can break code nobody in the review
owns. For them the onboarding cost is near zero, because the graph is already indexed: a
merge-request hook or the committed CI gate calls the Keystone API on the touched symbols and
fails the pipeline on a BLOCK.

It is not for a solo developer or a small team where the author already holds the whole graph in
their head, and it is not for a shop that is not on Orbit, because without the graph there is
nothing to compute the blast radius or the collision from. The wedge is deliberately narrow. What
makes it widen rather than stay niche is who is writing the merge requests: as autonomous coding
agents start authoring whole changes, a gate that binds a verifiable identity, refuses an agent
approving an agent, and records an impact nobody can quietly edit is exactly the missing control.

## Built with

python, fastapi, duckdb, gitlab-orbit, vanilla-js, html, css, github-actions, gitlab-ai-catalog,
openrouter, in-toto, slsa, hmac
