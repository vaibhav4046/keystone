# Keystone - Devpost submission text

Paste these into the Devpost fields. Written to be honest and specific. No em-dashes, no
hashtags, no invented numbers or users. Fill the links and the video URL where marked.

GitLab repo (PRIMARY - required by the rules): https://gitlab.com/lalwanivaibhav079/keystone   (public, MIT, synced to commit 6905589)
GitHub mirror (secondary): https://github.com/vaibhav4046/keystone
AI Catalog artifact: <PASTE CATALOG LINK - publish .gitlab/agents/keystone/agent.yml to the AI Catalog, then paste>
Live demo: https://vaibhav4046.github.io/keystone/
Video (public, under 3 min): <PASTE YOUTUBE OR VIMEO URL>

---

## What changed during the submission period (Path B)

The project existed before 5 October, so per the rules here is exactly what was built and
deployed afterwards. All of it is in the repository at the commit above, and all of it is
covered by the pipeline in `.gitlab-ci.yml`.

**1. Dependency-risk propagation (the `secure` stage).** A dependency scanner tells you
`fastapi` has a CVE. It cannot tell you which of your own code that touches. Keystone joins
the advisory to the graph:

```
advisory -> gl_imported_symbol (real import edges) -> gl_definition
         -> bounded reverse-BFS blast radius -> ALLOW / HOLD / BLOCK
```

Against the committed real Orbit self-index, a CRITICAL advisory on `duckdb` resolves to 2
importing files, 16 definitions, worst-case blast radius 6, owned by `core`, verdict BLOCK.
A HIGH advisory on `fastapi` resolves to `backend/app.py` and 11 definitions. A HIGH advisory
on `starlette` is reported as 0 entry points, because nothing imports it directly, rather
than as a clean bill of health. The engine refuses to guess: an unpinned version or an
unimplemented operator returns an explicit non-match, never a silent pass.

**2. Incident recall (the `monitor` stage).** Every gate here can report a blast radius all
day. Only an incident can say whether that number was right. This scores the engine's own
predictions against reality and returns precision, recall, and the set that broke without
ever being predicted. Against the shipped fixture: one incident held at recall 1.0, one was
PREDICTION_UNDERSTATED with a named missed symbol at recall 0.5, and one with no recorded
decision reported NO_BASELINE. The missed set is returned as concrete precedent updates,
because it is exactly the dependency the memory is missing.

**3. Configuration drift (the `configure` stage).** Keystone pins the policy hash into every
ledger row and, until now, never read it back. An edited `.keystone/policy.json` therefore
left every prior approval still recorded as valid, under rules that had stopped existing.
This reads the pins back and reports CURRENT, DRIFT, or UNKNOWN per row, with a re-review
queue that puts drifted approvals ahead of drifted rejections, because an approval earned
under a stricter policy is the expensive case.

Together these took the pipeline from 3 stages and 4 jobs to **7 stages and 11 jobs**, the
MCP server from 6 tools to **10**, and the test suite from 165 to **208 passing, 2 skipped**.

## Elevator pitch (one line)

Git sees files. Orbit sees relationships. Keystone catches hidden merge-request collisions before they ship, and then extends the same graph reasoning across the rest of the lifecycle: it turns a package advisory into a ranked blast radius, scores its own predictions against real incidents, and checks whether the rules a decision was recorded under still exist. The model proposes; the engine decides; the ledger remembers.

## Inspiration

As autonomous AI coding agents move from simple autocomplete to authoring complex, multi-file patches, they introduce a massive new safety risk. Agents propose code changes, but they have no accountability, cannot be paged at 2 AM, and do not understand the systemic consequences of their edits. Human reviewers skimming a diff cannot foresee when changing a utility function in one file silently breaks a dependency in another. Git sees files; Orbit sees relationships; Keystone sees consequences.

We built Keystone to act as the missing **governance and engineering harness** around coding agents. By wrapping agent proposals in a deterministic verification pipeline driven by the Orbit code graph, we ensure no agent-authored change reaches production without safety clearances and human-in-the-loop approvals.

The second half of the problem is worse and less discussed. A governance engine that is never
scored is decoration. An engine that is scored and quietly wrong is worse than none. So the
later work asks the engine to grade itself: did the predicted blast radius cover what
actually broke, and were the recorded decisions made under rules that still exist?

## What it does

Keystone turns code review from a passive dashboard into an active, deterministic merge controller, and then keeps the controller honest after the merge.

1. **The Engineering Harness**: A verification pipeline for agent-authored patches:
   - **Symbol Resolve**: Validates touched symbols exist in the Orbit graph.
   - **Blast Compute**: Computes the blast radius (impact depth, definitions, owners) using reverse-BFS.
   - **Policy Gate**: Maps blast impact to ALLOW, HOLD, or BLOCK policy tiers.
   - **Collision Scan**: Scans for cross-MR blast overlaps (hidden merge collisions) across open MRs.
   - **Verdict**: Decides if a change is safe to merge, suggesting a topologically sorted safe merge order.

2. **Cross-MR Blast Collisions**: Detects when two independent merge requests overlap in their call graphs (no Git conflict, but a dependency collision) and computes a safe merge sequence.

3. **Dependency-risk propagation**: Joins a package advisory to real import edges and computes which definitions are actually exposed, how far the damage travels, and which directory owns it. Severity alone does not block a release; propagated blast radius does.

4. **Incident recall**: Scores the engine's own precision and recall against real incidents, and returns the symbols that broke with no prediction behind them as precedent updates. An incident with no recorded baseline reports NO_BASELINE, never a pass.

5. **Configuration drift**: Reads back the policy hash pinned into every ledger row and reports which decisions were recorded under rules that no longer exist.

6. **Governance & Audit Trail**: Restricts autonomous agents from self-approving, enforces four-eyes rules, and commits all decisions to an HMAC-keyed, hash-chained ledger.

7. **Real AI, Off the Trust Path**: A bounded tool-using agent explains the impact and recommends reviewers, but never decides the verdict. The model proposes; the deterministic engine decides.

The command center is fully polished: a premium dark/light dashboard, an interactive merge collision simulator, and the animated **Engineering Harness visualizer** showing live pipeline state for agent-authored changes.

## How we built it

One pure-Python engine owns every number: it reads the Orbit Local graph (the DuckDB file Orbit
itself produces), computes the bounded reverse-BFS blast radius and the blast signature, detects
the cross-MR collisions and the safe merge order, maps the policy tier, and maintains the
hash-chained ledger. A single FastAPI app serves it. The web command center, a command-line skill,
the MCP server, and the CI gate are thin clients of that one core.

The integration with Orbit is direct and load-bearing: the engine reads Orbit's own graph
database, and the product also drives the real `orbit` CLI (`orbit schema` and `orbit sql`) at
session start and as a live cross-check. The public demo is not a mock. It is served from a real
`orbit index` of this very repository: 262 definitions, 689 relationships, 120 verified symbols,
and for every symbol it shows the exact `orbit sql` command and the count it returned. The build
is deterministic, so continuous integration rebuilds the bundle byte-for-byte and fails on drift.

Everything the later stages report is read from graph rows or from a pinned hash. The dependency
engine reads the real `gl_imported_symbol` import edges and the real `gl_definition` rows; the
recall scorer reads the real ledger; the drift checker recomputes the real policy hash. Advisories
are read from a local file rather than a live feed, so a CI run and a judge's re-run produce
byte-identical output and a flaky upstream cannot move a gate.

The AI runs on a free provider ladder (OpenRouter and others) behind hard timeouts, with a
deterministic fallback so the whole product works with zero API keys.

## How it uses the GitLab Duo Agent Platform and AI Catalog

The submission covers all three Duo Agent Platform surfaces.

**Agent.** A Duo Agent Platform agent at `.gitlab/agents/keystone/agent.yml`: a governed-review
persona with four fixed workflows and ten bound tools. The first is the original review workflow
(resolve the symbol on the Orbit graph, compute blast radius, surface precedent and contradictions,
require a human decision, verify the ledger). The second drives the supply-chain path, the third
the feedback path, and the fourth is an assurance pass whose hard rule is to describe configuration
drift as a fact about history rather than as wrongdoing. It is published to the GitLab AI Catalog so
other teams can install it.

**Flow.** A GitLab Flow at `.gitlab/flows/keystone-lifecycle.yml` runs the same engine as an ordered
pipeline, so nobody has to remember to call the checks in the right order: resolve the symbol, verify
the blast radius and policy verdict, propagate package advisories, gate the release, check the
recorded policy, score the engine's recall, and stop at a human decision. The Flow is not merely
declared: a CI job executes every step in order and then validates the Flow file itself, so a
shipped-but-broken Flow fails the build.

**MCP server.** `mcp/keystone_server.py` exposes all ten tools over Model Context Protocol, so any
MCP client can ask the graph for a verdict without the agent being the thing that produces it.

The same workflows ship as runnable scripts that need no server:

```
python skills/keystone/run_review.py <symbol> --local    # the review gate
python scripts/dependency_risk.py                        # advisory -> blast radius
python scripts/incident_recall.py                         # were the predictions right?
python scripts/config_drift.py                           # were the rules the same then?
```

Each takes `--fail-on-block`, `--fail-on-understated`, or `--fail-on-drift` to become an
enforceable CI gate that exits non-zero. That is the proof the agent automates an action rather
than chatting: it produces a deterministic report, a verdict, and a tamper-evident ledger row.

## How GitLab Orbit is used (specifically)

The engine reads the Orbit Local graph database directly (the DuckDB file `orbit index` produces:
`gl_definition`, `gl_edge`, `gl_file`, `gl_directory`, `gl_imported_symbol`) and drives Orbit's own CLI
(`glab orbit local schema`, `glab orbit local sql`) for live introspection and cross-check. The
blast radius is a bounded reverse-BFS over `gl_edge` CALLS rows; the cross-MR collision is the
intersection of two symbols' dependent sets; the dependency-risk propagation walks
`gl_imported_symbol` for real import edges and then reuses the same reverse-BFS. Remove the Orbit
graph and there is nothing to compute. The public demo serves a real `orbit index` of this repo
(262 defs) and a second real index of pallets/click (1,841 defs) so the hazard is shown on
recognizable code, not a toy.

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

The third was quieter and mattered more. The recall scorer reported a total miss on every single
incident at first. The cause was that the ledger stores the blast set as DuckDB row ids, and row
ids are assigned at index time, so comparing them against an incident's symbol names never
matches. The fix was to key on symbol identity, which is the same reasoning behind the existing
`blast_radius_signature_fqn`. An engine that is confidently, systematically wrong is a worse
outcome than one that is silent, and the only reason this was caught is that the demo was run
from a clean checkout rather than from a working tree.

## Accomplishments I am proud of

The trust boundary held all the way through. Across a lot of iteration, the rule never bent: the
engine computes every number from real graph rows, and the model is never allowed to produce a
number or a verdict. That is what makes the audit trail worth anything.

And the honesty of the demo. The numbers on screen are a real Orbit index of the repo, checkable
against the Orbit command shown. The status panel always says whether the data is live, a
committed snapshot, or a fallback fixture. The identity model is labeled exactly as strong as it
is and no stronger. The incident recall report says NO_BASELINE when it cannot check, and UNKNOWN
when a ledger row carries no policy hash, rather than rounding either one up to a pass.

## What I learned

Adversarial verification earns its cost. Every time I had a separate pass try to break a change
before committing it, it found something a passing test had missed.

The harder lesson was about assertions. Two of the three CI gates in this project are wired as
"this must fail", because their shipped demo data deliberately contains a blocking condition. I
copied that shape onto a third gate whose data has no such condition, and the pipeline went red
because a correct gate was not misbehaving. Asserting that a gate does *not* fire on a clean tree
is a different and more useful test than asserting that it does fire, and a gate that fires on a
clean tree is a gate people disable.

And the hardest part of a governance tool is not the enforcement, it is being precise and honest
about what the enforcement does and does not guarantee.

## What's next

Two graph-driven gates still need Orbit Remote data the free local graph does not contain, and are
documented rather than mocked: an ownership-entropy gate that catches stale owners, and a
pipeline-health risk multiplier. Each is one Orbit Remote query away.

The more interesting direction is the loop. Now that predictions can be scored against incidents,
the natural next step is feeding the missed-symbol set back into the precedent store automatically
on every incident, so the memory improves from production rather than from review. That is close
to working: `incident_recall.py` already emits the precedent updates, and what is missing is
writing them back under a policy decision rather than as a suggestion.

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
