# Keystone - First-Place Submission Pack (paste-ready)

Final copy. Paste each block where the form asks for it. The only steps that need YOUR account are
marked USER-ONLY (paste, deploy, record, submit). Every number is real and reproducible - see §"Judge
verification".

- **Live demo:** https://vaibhav4046.github.io/keystone/  (serves the winner-ready landing after `git push origin main`)
- **GitLab repo (PRIMARY - required by the rules):** https://gitlab.com/lalwanivaibhav079/keystone
- **GitHub mirror:** https://github.com/vaibhav4046/keystone
- **Live backend (Render, real agent + live orbit sql cross-check):** https://keystone-zt6c.onrender.com  (health: /api/health)
- **Track:** GitLab Transcend Hackathon - Showcase · **License:** MIT
- **The one command:** `python skills/keystone/run_review.py demo`

---

## Title
```
Keystone - consequence-aware merge governance on the GitLab Orbit graph
```

## Tagline
```
Git review sees files. Production breaks through relationships. Keystone uses GitLab Orbit to catch the merge collisions reviewers cannot see - and records the decision where no one can quietly edit it.
```

## Short description (≤ 280 chars)
```
Two merge requests can pass review, touch different files, have no Git conflict - and still break production together. Keystone reads the GitLab Orbit call graph, blocks those silent collisions before merge, gates AI-authored MRs, and logs every decision in a tamper-evident ledger.
```

## Long description
```
Keystone turns the GitLab Orbit code knowledge graph into a merge gate.

Git's conflict detection is textual - it only flags overlapping line edits. So two merge requests can change entirely different files, pass review independently, and still break production together, because one changes a function the other's change depends on. There is no text conflict, so Git, the MR diff, and CODEOWNERS are all blind to it. As AI coding agents open MRs faster than any human can hold the context between them, these silent collisions multiply.

Keystone computes each change's blast radius from the real Orbit call graph (gl_definition / gl_edge) and then:
- Shadow Merge Firewall: detects cross-MR collisions Git cannot see, classifies how dangerous each is (same_change / change_in_blast / blast_overlap), and returns a safe merge order from a topological sort - or reports the cycle that makes one impossible.
- Orbit Memory Gate: refuses an approval that contradicts a prior identical-blast rejection, so project memory overrules even an AI agent's APPROVE.
- Agent governance: gates autonomous coding agents against a committed scope manifest and binds each decision to a verifiable identity (GitLab OIDC on the CI path).
- Tamper-evident ledger: every approve/reject is appended to an HMAC-SHA256 hash-chained log; change one row and the whole chain visibly breaks.

The decision path uses no LLM - every figure is computed from a real orbit index and cross-checked by a live `glab orbit local sql` query that returns the same number. 116 tests pass. The same engine that runs on Keystone's own 262-definition index also finds genuine collisions on pallets/click (1,841 definitions) - a library it did not write - so it is not tuned to our own code. An optional AI assistant explains a change in plain language but is advisory only: it proposes, the deterministic gate decides.
```

## What it does
```
- Surfaces "silent collisions": MR pairs that pass review and touch different files yet share a runtime dependency, so they break together once both merge.
- Blocks the dangerous merge before it lands and hands back a safe merge order.
- Overrules any approval - human or AI agent - that contradicts a prior identical-blast rejection.
- Gates AI agents to a committed file/blast scope and binds CI decisions to a GitLab OIDC identity.
- Records every decision in an HMAC-SHA256 hash-chained ledger you can re-verify and watch break under tampering.
```

## How we built it
```
- GitLab Orbit Local: `glab orbit local index` builds the call graph into a DuckDB file (gl_definition / gl_edge). Keystone reads it directly (fast path) AND drives Orbit's own CLI (`glab orbit local sql`) once per session to cross-check every number.
- Engine: pure-Python, deterministic. core/impact.py (bounded reverse-BFS blast radius), core/collision.py (cross-MR classification + Kahn topological safe-merge-order), core/gate.py (one shared enforcement decision used by both the API and CI), core/audit.py (HMAC-SHA256 hash chain), core/policy.py (blast→tier→ALLOW/HOLD/BLOCK), core/identity.py (GitLab OIDC binding with RS256/JWKS verification).
- Surfaces: a FastAPI backend, a static browser demo (no backend needed), a runnable Open Agent SKILL.md, and a .gitlab-ci.yml gate that fails the pipeline on a BLOCK.
- Optional AI assistant: a bounded tool-using agent (free-model ladder) that calls the deterministic engine tools then explains - never computes a number or a verdict.
```

## Best use of GitLab Orbit
```
Keystone is impossible without Orbit. Git and CODEOWNERS see files; Orbit's gl_definition/gl_edge call graph is the ONLY place the relationship between two file-disjoint changes exists. Keystone:
- reads the real Orbit graph (committed `orbit index` of 262 definitions on the deploy),
- drives Orbit's own `glab orbit local sql` to cross-check 120/120 ring-1 counts against the engine,
- and runs the SAME engine on a third-party Orbit index (pallets/click, 1,841 defs) to prove generality.
Blast radius and cross-MR collision are direct computations over Orbit's symbol graph - language-agnostic, because they run on the graph, not on any one language's syntax.
```

## Why this is technically real
```
- Deterministic: same graph in, same rings/counts/verdict out. No model on the decision path.
- Cross-checked: each ring-1 count is verified against a live `glab orbit local sql` query; a raw-SQL independent recompute is asserted in tests.
- Reproducible in one command: `python skills/keystone/run_review.py demo` → BLOCK (exit 2), ALLOW (exit 0), AI override, ledger break.
- Tested: 116 passing tests, including the cross-MR collision, the memory-gate override, content-addressed precedent, and a real collision on pallets/click.
- Honest about its seams (labelled in the UI): FNV-1a hash in the static browser demo vs HMAC-SHA256 in production; self-asserted identity in the static demo vs OIDC-bound on CI.
```

## What makes it different
```
- Branch protection / required approvers gate WHO and HOW MANY, not WHAT BREAKS. Keystone gates the graph consequence.
- Signed commits / Sigstore / in-toto prove WHO authored/built; Keystone proves the change was SAFE given the graph, and records why.
- Generic "AI code review" bots summarise a diff with an LLM; Keystone's verdict is a deterministic graph computation an auditor can re-run - the LLM only explains.
- The cross-MR silent collision + safe merge order is a capability neither Git, the MR diff, CODEOWNERS, nor CI surfaces today.
```

## Challenges we ran into
```
- The first build used a fictional graph schema; the live `orbit index` exposed it, and we rebuilt every query to Orbit's real gl_* tables.
- Matching the engine's blast count to Orbit's SQL exactly required `count(DISTINCT source_id) ... AND source_id<>target_id`, not a raw count.
- The multi-symbol MR union could RELAX the gate; an adversarial pass + a brute-force over all 2,925 pairs/triples (0 inversions) caught and fixed it.
- Precedent keyed on volatile DuckDB row ids missed after a re-index; we made it content-addressed over the epicenter + affected FQN set.
```

## What's next
```
- Live MR webhook + a diff→changed-symbols first mile so the gate runs on a real GitLab MR automatically.
- Orbit Remote enrichment (security findings, ownership, pipeline health) behind a flag.
- Asymmetric (Sigstore/transparency-log) ledger anchoring for insider-grade tamper resistance.
- A second indexed OSS repo + a historical incident to quantify prevented-incident impact.
```

## Judge verification steps (in 2 minutes, no trust required)
```
1. python -m pytest -q                                   -> 116 passed, 2 skipped
2. python skills/keystone/run_review.py demo             -> the whole story: BLOCK / ALLOW / AI override / ledger break
3. Open the live demo -> Try the live demo -> green "REAL GitLab Orbit graph" badge -> Reviewer Cockpit (blast graph) -> Audit Ledger -> Simulate tamper (chain BROKEN) -> Restore
4. python skills/keystone/run_review.py shadow-merge --graph data/click_graph.duckdb --a Context --b echo   -> a real collision on a repo we did not write
5. README "How to verify this is real" maps every claim to a check.
```

---

## AI Catalog submission description (the catalog field)
```
Keystone is a deterministic, GitLab-native merge-governance engine built on the Orbit code knowledge graph. It surfaces "silent collisions" - pairs of merge requests that pass review and touch different files yet break production together because they share a runtime dependency - and blocks them before merge with a safe merge order. It gates AI-authored merge requests against a committed scope manifest, overrules any approval (human or agent) that contradicts a prior identical-blast rejection, and records every decision in an HMAC-SHA256 hash-chained, tamper-evident ledger bound to a GitLab OIDC identity on the CI path.

The decision path uses no LLM: every blast-radius and collision figure is computed from a real orbit index and cross-checked by a live `glab orbit local sql` query. An optional AI assistant explains changes in natural language but is advisory only. Proven on the project's own 262-definition index and on a third-party repo (pallets/click, 1,841 definitions). Open source (MIT). One command reproduces the whole demo: `python skills/keystone/run_review.py demo`.
```

---

## Video script - 2:30, pain-first, cinematic (USER-ONLY: record)

> Say only the quoted lines. [ACTION] cues are for you. Screen-record terminal + browser. No architecture talk until 2:10.

```
[0:00-0:20] HOOK  [SCREEN: terminal]
"Git review sees files. Production breaks through relationships. Two merge requests can pass
review, touch completely different files, have zero Git conflict - and still take down
production together. Keystone uses GitLab Orbit to catch exactly that."

[0:20-0:50] TWO SAFE MRS BECOME DANGEROUS  [ACTION: run the one command]
$ python skills/keystone/run_review.py demo
"MR-204 speeds up compute_blast_radius. MR-207, in a different file, edits impact() - a
function that depends on it. Git says: no conflict, two unrelated files."

[0:50-1:20] KEYSTONE BLOCKS WITH ORBIT PROOF  [ACTION: point at beat 1-3]
"On the Orbit call graph, MR-207's change lands inside MR-204's blast radius. Keystone calls it
a directional collision and BLOCKS the merge - exit code 2, the pipeline fails. Then a safe,
non-overlapping pair: ALLOW, exit 0. It blocks the danger, not everything. No model decided
this - it's a deterministic graph computation, cross-checked by Orbit's own SQL."

[1:20-1:45] AI APPROVAL OVERRULED BY MEMORY  [ACTION: point at beat 5]
"A staff engineer rejects a risky change. Then a coding agent proposes APPROVE on the same
thing. Keystone recalls the rejection it recorded seconds ago - by content, so it survives a
rename or a re-index - and overrules the agent. The model proposes; Keystone decides."

[1:45-2:10] LEDGER TAMPER + TRUST  [ACTION: point at beat 6, then the live Audit Ledger]
"Every decision is hash-chained. Edit one past approval - the whole chain breaks at that row.
On the live site, hit Simulate tamper and watch it happen, then Restore. No one edits an
approval quietly."

[2:10-2:30] WHY IT MATTERS  [SCREEN: live landing, badges]
"AI agents now write code faster than humans can review the relationships between changes. Git
conflicts aren't enough. Keystone is the missing gate - built on GitLab Orbit, deterministic,
auditable, and it already finds real collisions on third-party repos. Git sees files. Orbit
sees relationships. Keystone sees consequences."
```

**Recording sequence (exact):** large terminal → run `demo` once (covers beats 1-6) → browser
https://vaibhav4046.github.io/keystone/ → Try the live demo → green Orbit badge → Reviewer Cockpit
(graph) → Audit Ledger → Simulate tamper → Restore → back to landing (show the proof badges). Under 2:30.

---

## Impact story (for the Potential-Impact field / judge notes)
```
AI agents now create more code, faster, than any review process was designed for. A human
reviewer can read a diff; they cannot hold the relationship-level blast radius of every parallel
change in their head. Git conflicts only catch text overlap. So the failure mode is no longer "two
people edited the same line" - it is "two safe-looking changes, in different files, that break
together because they share a runtime dependency." That class of incident grows with every agent
added to the pipeline.

Concrete: MR A changes the blast-radius engine. MR B changes a verifier that runs inside that
blast radius. Git says safe. Both pass review. Merged together, the verifier runs against the new
contract and breaks - a 2am page, a rollback, a post-incident hunt for who approved what. Keystone
puts the collision and the safe merge order in front of the reviewer at approval time, and leaves a
record the audit can trust. As GitLab Duo and AI-native development scale, the value compounds:
more parallel agent-authored changes = more silent collisions = more need for a graph-aware gate.
```

---

## Deployment + live-proof checklist

USER-ONLY - ship the fixes (the winner-ready branch is local until you push):
```bash
git checkout main
git merge --no-ff winner-ready -m "Merge winner-ready: first-place strike package"
git push origin main      # GitHub - drives the GitHub Pages live demo
git push gitlab main      # GitLab - the PRIMARY submission repo (run `glab auth login` first if needed)
```

USER-ONLY - verify the live demo after push (the public verification checklist):
- [ ] https://vaibhav4046.github.io/keystone/ loads; hero reads "Merge requests that break together".
- [ ] The proof badges + "Judges - watch this first" panel are visible above the fold.
- [ ] "Try the live demo" → green "REAL GitLab Orbit graph" badge appears.
- [ ] Reviewer Cockpit → the blast graph renders (nodes + edges, not empty).
- [ ] Audit Ledger → "Simulate tamper" turns the chain BROKEN; "Restore"/"Verify chain" re-validates.
- [ ] "Demo on pallets/click" loads the 1,841-def third-party graph.
- [ ] Mobile (DevTools 375px): no horizontal scroll; buttons are tappable.

USER-ONLY (recommended, #1 remote-judge lever) - one-click live backend on Render:
- [ ] render.com → New → Blueprint → connect the GitHub repo → Apply (free tier, no card; uses render.yaml).
- [ ] `curl -s https://<your-render-url>/api/health` returns ok.
- [ ] (Optional) add OPENROUTER_API_KEY under Environment for the real LLM brief + agent. Never commit it.
- [ ] `curl -sI https://<your-render-url>/ | grep -i content-security-policy` shows the header.

USER-ONLY - submit:
- [ ] Record the 2:30 video (script above) → upload YouTube/Vimeo unlisted.
- [ ] Publish the AI Catalog agent (GitLab browser sign-in) with the catalog description above.
- [ ] Fill Devpost with the fields above + repo + live + video links; SUBMIT; verify status reads SUBMITTED (screenshot it).
- [ ] Post-hackathon: rotate the .env keys.
```
