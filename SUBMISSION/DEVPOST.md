# Keystone — Devpost submission text

Paste these into the Devpost fields. Written to be honest and specific. No em-dashes, no
hashtags, no invented numbers or users. Fill the two links and the video URL where marked.

Repo: https://github.com/vaibhav4046/keystone
Live demo: https://vaibhav4046.github.io/keystone/
Video: <PASTE YOUTUBE OR VIMEO URL>

---

## Elevator pitch (one line)

Keystone X-rays the hazards in the GitLab Orbit code graph that the review surface structurally
cannot see, then governs the change with a deterministic, tamper-evident gate.

## Inspiration

The same incident kept happening on teams I read about and worked near. Two merge requests, two
different people, two different files. Neither has a merge conflict. Both pass review. They merge,
and something breaks, because one of them changed a function the other one depended on. When you
go back to figure out what happened, the review record is thin: an approval with no rationale, a
log you cannot fully trust because it was editable, and no record of the impact anyone actually
weighed. Git is built around text. The thing that breaks you is the call graph, and nothing in the
normal review surface shows it.

GitLab Orbit builds that call graph. So the question became simple: what can you see, and what can
you refuse, once you have the graph at the moment of review.

## What it does

Two hazards first, because they are the part nobody else shows you.

The first is a cross-MR blast collision. Point Keystone at a set of open merge requests and it
finds the pairs whose blast radii collide on the call graph even though there is no Git conflict,
classifies how dangerous each collision is, and computes a safe merge order with a topological
sort (or reports the cycle that makes a safe order impossible). On the live demo you can add your
own open merge request and watch the collisions and the merge order recompute in the browser.

The second is review debt: the symbols with a large blast radius that no test file directly
exercises, ranked. High impact and unverified is exactly the change you want flagged before it
merges, and the graph can find those deterministically.

Then it governs. Orbit gives the blast radius of a single change. Keystone maps that radius to a
policy tier that sets the required number of approvers and an ALLOW, HOLD, or BLOCK action. It
refuses an approval that contradicts a prior rejection of the same blast signature. It gates
autonomous coding agents against a committed scope manifest. It enforces four-eyes so an author
cannot approve their own change. And it records every decision in an HMAC-keyed, hash-chained
ledger whose integrity is recomputed live, with a standards-shaped attestation bound to the exact
graph context the reviewer saw.

There is a real AI layer, deliberately kept off the trust path. A bounded tool-using agent calls
the deterministic engine for the blast radius, the precedent, and the suggested reviewers, then
recommends a next step, and you can see the exact tools it called. It never produces a number and
it never records a decision. The model proposes, the deterministic gate decides.

## How we built it

One pure-Python engine owns every number: it reads the Orbit Local graph (the DuckDB file Orbit
itself produces), computes the bounded reverse-BFS blast radius and the blast signature, detects
the cross-MR collisions and the safe merge order, maps the policy tier, and maintains the
hash-chained ledger. A single FastAPI app serves it. The web command center, a command-line skill,
and the CI gate are thin clients of that one core.

The integration with Orbit is direct and load-bearing: the engine reads Orbit's own graph
database, and the product also drives the real `orbit` CLI (`orbit schema` and `orbit sql`) at
session start and as a live cross-check. The public demo is not a mock. It is served from a real
`orbit index` of this very repository, 262 definitions, and for every symbol it shows the exact
`orbit sql` command and the count it returned, with 120 of 120 symbols cross-verified. The build
is deterministic, so continuous integration rebuilds the bundle byte-for-byte and fails on drift.

The AI runs on a free provider ladder (OpenRouter and others) behind hard timeouts, with a
deterministic fallback so the whole product works with zero API keys.

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

python, fastapi, duckdb, gitlab-orbit, vanilla-js, html, css, github-actions, openrouter,
in-toto, slsa, hmac
