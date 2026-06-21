# WIN NOW - the exact path to 1st place (do these 3, in order)

The product is winner-grade and verified across all four judged axes. The ONLY thing
between Keystone and a prize is submission - an unsubmitted project scores zero on every
axis no matter how good it is. These three steps are login-gated (only you can do them);
everything they need is below, paste-ready. Budget: ~25 minutes total.

Deadline: **2026-06-24 14:00 EDT**. Win model: top-2 in any ONE of four equal axes.

---

## STEP 1 - Publish to the AI Catalog (HARD REQUIREMENT, ~5 min)

The Showcase track REQUIRES ">=1 agent or flow published to the AI Catalog." Without
this, the entry fails the Stage-1 gate and is not judged at all. Do this first.

1. In your GitLab project (gitlab.com/lalwanivaibhav079/keystone), open the **Duo Agent
   Platform / AI Catalog** publish flow for the Keystone skill (`skills/keystone/SKILL.md`).
2. Publish the **Keystone governed-review skill** (the agent that runs `run_review.py` /
   the gate). Title: `Keystone - the merge gate for AI coding agents`.
3. Copy the published AI Catalog URL -> paste it into Devpost (STEP 3).

If the platform asks for a one-line description, use:
> Deterministic, no-LLM merge gate on the GitLab Orbit graph: catches cross-MR blast
> collisions and holds AI-agent merges that contradict recorded precedent.

---

## STEP 2 - Upload the demo video (HARD REQUIREMENT, ~8 min)

The asset already exists and is verified: `SUBMISSION/keystone-demo.mp4` (~97s) and it
already autoplays in the hero on the live site. Upload a public copy:

1. YouTube Studio -> Create -> Upload -> select `SUBMISSION/keystone-demo.mp4` (or record
   a fresh 75s take from the script below for a sharper voiceover).
2. Visibility: **Public** (the rules require public YouTube/Vimeo). Title:
   `Keystone - merge requests that break together`.
3. Copy the watch URL -> Devpost (STEP 3).

**75-second script (if you re-record):**
- 0:00 hook: "Two merge requests each pass review, but both change code a shared function
  depends on - so they break together in production. Keystone catches that before merge."
- 0:10 sign in with GitHub -> your repos appear.
- 0:25 Reviewer Cockpit -> "Gate as an AI-agent MR" -> live server verdict; then the
  "Run REAL duckdb-wasm SQL in your browser" button -> the count matches.
- 0:45 terminal: `python skills/keystone/run_review.py scan-repo benjaminp/six` -> "any
  repo, zero pre-indexing"; then `git diff | run_review.py changed-symbols --fail-on-block`.
- 1:00 Audit Ledger -> Simulate tamper (chain breaks) -> Restore.
- 1:10 close: "Git sees files. Orbit sees relationships. Keystone is the autonomous merge
  gate that holds AI coding agents accountable."

---

## STEP 3 - Submit on Devpost (~10 min) - paste these fields

Open gitlab-transcend.devpost.com -> Submit. Paste:

- **Project name:** Keystone
- **Tagline:** The first merge gate for AI coding agents - on the GitLab Orbit graph.
- **Elevator pitch:** Two merge requests each pass review, touch different files, have no
  Git conflict, and still break production together because one changes a function the
  other depends on. Keystone reads the GitLab Orbit code graph to catch that cross-MR
  blast collision before merge - and holds AI-agent merges that contradict recorded
  precedent. Deterministic, no LLM on the verdict.
- **What it does:** Detects cross-MR blast collisions on the Orbit graph; computes a safe
  merge order; gates every change (human or AI agent) with a deterministic ALLOW/HOLD/
  BLOCK verdict and required approvers; overrules an AI agent's self-approval that
  contradicts a recorded rejection; records every decision in a tamper-evident HMAC ledger.
- **How we built it:** GitLab Orbit (gl_definition/gl_edge) as the code knowledge graph;
  a pure-Python deterministic engine (blast radius, collision, policy, audit); a FastAPI +
  DuckDB backend; a static GitHub Pages console. The SAME reverse-CALLS Orbit SQL runs
  three independent ways - server-side via the backend, in the browser via duckdb-wasm,
  and in the test suite - and they all converge (ring-1 = 12 on the headline symbol).
- **Best use of GitLab Orbit:** The verdict is a deterministic computation over Orbit's
  gl_definition/gl_edge graph - cross-MR transitive intersection - cross-checked by Orbit's
  own `orbit sql`. And `scan-repo` builds the same Orbit schema on the fly for ANY repo, so
  the control runs with zero pre-indexing.
- **Technical implementation:** 124 passing tests; no LLM on the verdict path; real GitHub
  OAuth (HttpOnly cookie); autonomous `git diff -> changed-symbols` gate; in-browser
  duckdb-wasm recompute; a live backend kept warm by a cron.
- **What makes it new:** It reveals a hazard Git, CODEOWNERS, branch protection, and merge
  trains structurally cannot see (they compare files; this reads the call graph), and it is
  the first gate built specifically to hold autonomous coding agents accountable.
- **Challenges / what we learned:** see DEVPOST.md.
- **What's next:** ownership-entropy gate (CODEOWNERS + commit recency), posting verdicts
  back as GitLab MR notes, GraphSource adapters beyond Orbit.
- **Built with:** GitLab Orbit, Duo Agent Platform, Python, FastAPI, DuckDB, duckdb-wasm,
  GitHub OAuth.
- **Links:** Live demo https://vaibhav4046.github.io/keystone/ - Backend
  https://keystone-zt6c.onrender.com/api/proof - Repo (GitLab)
  https://gitlab.com/lalwanivaibhav079/keystone - Repo (GitHub)
  https://github.com/vaibhav4046/keystone - Video: <paste STEP 2 URL> - AI Catalog:
  <paste STEP 1 URL>
- **Judge verification (paste in the description):**
  `python -m pytest -q` -> 124 passed; `run_review.py demo`; `run_review.py shadow-merge`
  (BLOCK, exit 2); `run_review.py scan-repo benjaminp/six` (any repo, zero pre-indexing);
  `curl .../api/proof`. On the live site: "Run REAL duckdb-wasm SQL in your browser" returns
  the same count as the backend; Simulate tamper breaks the live hash chain.

---

## Why it places top-2 per axis (judge notes)

- **Technological Implementation (strongest):** real Orbit SQL converging three ways
  (backend + duckdb-wasm in-browser + tests), deterministic no-LLM gate, autonomous diff
  gate, any-repo scan. 124 tests.
- **Quality of the Idea:** cross-MR blast collision + the AI-agent-accountability gate is a
  capability no file-diff tool can reproduce and GitLab doesn't ship.
- **Design & Usability:** one-CTA hero, autoplaying demo, hands-free tour, real navigation,
  live backend badge, zero console errors, no overflow 320-1440px.
- **Potential Impact:** `scan-repo` makes it a CI control ANY team can run (not just
  Orbit-Local orgs); the AI-agent-merge trend makes the problem grow.

Submit, and it is in the running. Don't, and it scores zero. The code is done.
