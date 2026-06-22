# Keystone — winner loop handoff (run this in a fresh session)

You are taking over Keystone (GitLab Transcend Hackathon, Showcase track). Your job: run an
autonomous loop — **judge panel → fix every code-fixable finding → re-test → re-panel** — to
push the product to its honest ceiling and keep it bulletproof. Read this whole file first,
then the repo and the memory file, then start the loop.

## The one hard truth you must not lie about (to the user or yourself)

The user wants "a 10 from every judge, never loses." **Code alone cannot deliver that, and you
must say so plainly.** The judge panel has been run; it is unanimous on *why* this won't win as
it stands, and only ONE of the reasons is code:

1. **Submission stage-gates are unmet (the dominant reason — NOT code).** The Showcase track
   hard-requires: an MIT skill on the GitLab Duo Agent Platform using Orbit (exists in repo),
   a **public <3-min video** (rendered locally, NOT published), **≥1 agent published to the AI
   Catalog** (NOT done — needs GitLab login), and a **filed Devpost submission** (drafted, NOT
   filed). Any one missing = disqualified-before-judging. **Only the user can do these.** No
   amount of engineering changes it. Every judge rated win-likelihood "low" because of this.
2. **Code-fixable caps** (this is your job): credibility bugs, Impact axis (Python-only),
   correctness/robustness regressions. Fix these to make the product winner-*grade*.

So: do NOT promise the user a guaranteed win or a literal "10 from all judges." Drive the
product to its ceiling, fix every code finding, and report honestly. A perfect-10 panel is not
a realistic convergence target while the gates are open; a *no-code-objections* panel is.

## Stopping condition (so the loop converges instead of burning forever)

Stop the loop when EITHER:
- two consecutive judge-panel rounds surface **zero new code-fixable findings** (only the
  submission gates + subjective taste remain), OR
- the only remaining objections are the submission gates / "more feature than company" /
  language coverage already at your scoped limit.
Then write an honest status and hand back to the user for the submission steps. Do not loop on
subjective design taste or re-litigate the submission gates.

## Current state (as of HEAD 2a2957d, both remotes origin=GitHub + gitlab synced)

- **132 pytest pass**, 2 skipped. Backend imports (33 routes). Both MCP servers self-test OK.
- **Three adversarial audit rounds done** (24 + 14 + 8 findings, all fixed except one deferred
  latent off-path flag: shadow-merge `--fixture` defaults). A CRITICAL self-inflicted
  tamper-evidence regression (atomic-append silently purging corrupt rows) was caught in
  round 2 and reversed (append is append-only + refuses on corruption).
- **Judge panel run** (8 personas): avg Technical 8.3, Idea 8.3, Design 7.0, Impact 6.5;
  6/8 "top-2 in an axis", 0/8 "overall winner", 8/8 win-likelihood "low" (submission gates).
- **Hero flow** (the #1 demo lever) is honest + reproducible after the panel's credibility fix:
  scan a repo → find a genuinely-independent cross-MR collision → draft/open a guard PR.
  Verified reproducible numbers (judge runs `find_top_collision` on the committed graph):
  - pallets/click → `Parameter x HelpFormatter`, **64 shared dependents** (from committed
    `data/click_graph.duckdb`, the real Orbit index — reproducible).
  - psf/requests → `values x set_cookie`, 48 ; benjaminp/six → `_resolve x __get_module`, 3.
  - Counts EXCLUDE the two changed symbols; tests are EXCLUDED from scans (a blast radius is
    production coupling, not how many tests touch a symbol).

## The autonomous loop — exact steps

1. **Sync + battery.** `cd D:\project\keystone`; `python -m pytest -q` (expect 132+ pass);
   `python mcp/keystone_server.py --selftest`; `python mcp/continuity_server.py --selftest`;
   `python -c "import sys;sys.path.insert(0,'.');from backend import app"`.
2. **Run the judge panel** (Workflow tool, ultracode is on). Reuse the saved script:
   `Workflow({scriptPath: "<session>/workflows/scripts/keystone-judge-panel-*.js"})` — or
   re-author it: 8 grounded GitLab-Transcend-Showcase personas (GitLab staff/Orbit, dev-tools
   PM, security lead, AI-agents researcher, hackathon veteran, skeptical principal, OSS
   maintainer, impact/VC), each FACT-CHECKS the repo (Read/Grep/Bash) and scores the 4 axes
   1-10 with `facts_that_failed`. Feed it the verified facts (above) so judges have ground
   truth and verify against real code. It returns structured scorecards.
3. **Triage the panel result.** Take every `facts_that_failed` + `blockers` that is
   code-fixable (NOT the submission gates). Sort by severity.
4. **Fix.** For each, edit the real file, add/adjust a regression test, re-run pytest, commit
   with a clear message + push BOTH remotes (`origin` and `gitlab`).
5. **Re-panel.** Go to step 2. Apply the stopping condition above.
6. **Honest report** each round: the table (persona × 4 axes), what you fixed, what remains,
   and the plain truth on win-likelihood.

Also run the **adversarial code audit** the same way between panels when you make engine
changes — it catches self-inflicted regressions (round 2 caught a critical one you introduced):
5 finder dimensions (backend-security, engine-correctness, mcp-robustness, frontend, harness),
each finding adversarially verified, only confirmed bugs returned, regressions flagged.

## Code-fixable backlog (the real levers, in priority order)

1. **Impact axis (6.5, lowest) — multi-language.** Python `ast` is sound; JS/TS is regex
   name-matching (approximate). Real JS/TS support (tree-sitter, accurate edges) is the
   honest lever to lift Impact and "everyone can use it." This is the biggest *winnable* delta.
   Largest build; scope it.
2. **Live scan reality.** Anonymous scan of a non-cached repo returns SCAN_FAILED (GitHub
   rate limit). Signed-in uses the user's token (works). Consider an optional server token via
   env so the public demo path works without sign-in.
3. **Name-based resolution honesty.** Even Python is name-based (dynamic dispatch
   under-approximated). Keep counts defensible; never headline a number that doesn't reproduce
   on a committed graph (the round that just shipped fixed exactly this — don't regress it).
4. **Design axis (7.0).** Subjective; do not loop on it. One real improvement only if a judge
   names a concrete defect.

## Verified commands + gotchas (save yourself the pain)

- **Local browser verify** (live SPA is dc-runtime React): `cd web && python -m http.server 8899`,
  then Chrome MCP to `http://127.0.0.1:8899/index.html`. The deployed backend CORS only allows
  the github.io origin, so `/api/*` fetches FAIL from localhost — verify API flows on the LIVE
  site (`https://vaibhav4046.github.io/keystone/`) after CI deploys, not on localhost.
- **Deploys:** push to `origin` (GitHub) → Pages redeploys `web/`; Render redeploys the backend
  from origin main. Both take ~1-3 min + a cold start. Poll the endpoint until live.
- **Dep pin:** `pip install mcp` upgrades starlette and breaks fastapi<0.116 — `requirements.txt`
  pins `starlette>=0.40,<0.46`. Keep it.
- **Hero cache:** `data/hero_collisions.json` is precomputed REAL collisions served instantly
  (no rate limit). pallets/click MUST be computed from the committed `data/click_graph.duckdb`
  so it reproduces; a regression test pins this (`test_hero_cache_click_reproduces_*`). If you
  change `find_top_collision`, regenerate the cache and keep the test green.
- **GateGuard fact-forcing hook:** before the first edit/creation of each file you must state
  importers/callers, affected API, data schemas, and the user's verbatim instruction, then
  retry. (`ECC_GATEGUARD=off` disables it.)
- **Foreground `sleep` is blocked.** Poll via background commands; you're notified on completion.
- **Workflow runs in background**, notifies on completion; parse its `confirmed`/`cards` from
  the output file (it truncates in the notification — read the full file).
- Memory lives at `C:\Users\lalwa\.claude\projects\D--\memory\project_keystone.md` (append-only;
  it has the full session history, every fix, and every gotcha). Read it.

## Definition of done (honest)

The product is "winner-grade" when: a fresh judge panel surfaces **no new code-fixable
finding** for two rounds, every headline number reproduces on a committed artifact, the full
battery is green, and the hero flow works live. At that point the ONLY thing between Keystone
and the prize is the submission (video + AI Catalog + Devpost) — which is the user's to do.
Report that plainly. Do not claim a guaranteed win; claim a defensible, reproducible, top-2-
quality product and name the exact remaining user-gated steps.
