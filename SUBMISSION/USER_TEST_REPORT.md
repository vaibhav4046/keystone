# Keystone - QA / user-test report

Date: 2026-06-21. Method: 10 independent persona judges scored the LIVE product
(https://vaibhav4046.github.io/keystone/) against a neutral capabilities brief
(which included the honest limits, to avoid priming) and the 10 user-test
questions. Run as a workflow in waves; synthesis was quorum-guarded (means only
emitted with >=7 real scorecards). 10/10 returned valid scorecards.

## Result

- **Mean 7.4 / 10, median 7.5.**
- **Comprehension was unanimous (10/10) on all 9 substantive questions:** understands
  the product in 10 seconds, understands why Git/CODEOWNERS miss it, understands why
  Orbit matters, trusts the deterministic verdict, sees that no LLM decides, sees the
  live backend, sees the external-repo proof, understands the agent fix plan, knows
  what to click next.
- **Would rank top-1: 2 / 10.** That is the whole gap: the product is understood and
  trusted; winner-likelihood is held back by packaging/positioning, not the product.

| Persona | Score | Top-1 |
|---------|-------|-------|
| Tired judge (90s) | 8 | yes |
| GitLab Staff Engineer | 7.5 | no |
| GitLab Orbit engineer | 7.5 | no |
| Security reviewer | 8 | no |
| Product manager | 7 | no |
| AI skeptic | 8 | yes |
| DevRel judge | 8 | no |
| OSS maintainer (monorepo) | 6 | no |
| Startup founder | 7 | no |
| Previous hackathon winner | 7 | no |

Panel verdict (synthesis): *"Strong, unusually honest entry... comprehension was
unanimous... The ceiling is not the product but the packaging and positioning: only
2 of 10 would rank it top-1, held back by an un-uploaded demo video and an unsubmitted
Devpost (existential, non-code), an Orbit/Ultimate-narrowed TAM, and a thin moat
against GitLab itself."*

## Fixes applied this session (code-fixable findings)

| Finding (raised by) | Status | What changed |
|---------------------|--------|--------------|
| `/api/status` leaks the dev abspath `D:\project\keystone` (security reviewer) | **Completed** | `_clean_repo()` basenames any absolute repo path; clean labels (`pallets/click`) pass through. +1 test asserts no drive letter / backslash leaks. (`73d6c94`) |
| No "why GitLab/merge-train can't just ship this" rebuttal on the demo; impact math only in README (staff eng, founder, Orbit eng, PM, prev-winner) | **Completed** | A "Why Git and GitLab can't catch this" card on the landing contrasts Git diff / CODEOWNERS / branch-protection+merge-trains vs Keystone's transitive cross-MR graph intersection + precedent memory, with an honest DORA-class impact line (no fabricated dollar). (`00e0250`) |
| Free-tier cold start degrades the "Live backend verified" badge to snapshot on first paint (DevRel, prev-winner, tired judge) | **Completed** | Warm-up `/api/health` ping on load + an honest "Live backend warming" state that retries (~50s) instead of instantly showing "asleep". (`00e0250`) |
| "Orbit" unglossed; competing CTAs; no who-it-is-for (tired judge, PM, DevRel, founder) | **Completed** | Inline "Orbit (GitLab's code knowledge graph)" gloss + a who-it-is / is-NOT-for qualifier (parallel MRs on a large shared codebase; not a solo/linear repo). (`00e0250`) |

## Honestly deferred (judged lower-leverage or higher-risk than the above)

- One-click in-UI "verify determinism" recompute and a browser WebCrypto HMAC that
  matches the prod hash (the demo uses FNV-1a, labelled): real but larger; trust
  already scored 10/10, so lower marginal value this pass.
- Paste-a-diff -> changed-symbols generality and a non-Python repo: needs a diff
  parser + a second indexed graph; research-shaped.
- Rendering Orbit `gl_edge` edge TYPES (calls vs imports) and the live `orbit sql`
  cross-check transcript in the Cockpit: deepens the Orbit story; deferred for scope.
- A server-side real-HMAC chain-verify endpoint + showing IDENTITY_MISMATCH /
  SELF_APPROVAL firing live: these already pass in the test suite.

## Blockers (non-code; cannot be closed from this environment)

1. **Demo video not uploaded** (the asset `SUBMISSION/keystone-demo.mp4` exists; the
   unlisted YouTube/Vimeo upload is login-gated). Flagged by 9/10 as the single
   largest non-code win-blocker.
2. **Devpost / AI Catalog not submitted** (login-gated; an unsubmitted project is
   judged on zero axes).
3. **TAM:** Orbit needs GitLab Ultimate; the addressable market is large-monorepo
   Ultimate accounts. Not code-fixable; needs market/design-partner evidence.
4. **Thin moat vs GitLab itself** and **no validated buyer signal** - positioning /
   evidence problems, not product defects.

## Honest takeaway

Scored as a product, Keystone is a credible top-2 contender in Technological
Implementation and Quality of the Idea (comprehension + trust are unanimous). It is
not a measured first-place lock: the binding constraints are the login-gated
submission steps and a structurally narrow TAM, neither of which is code-fixable.
This is the honest number; it is not inflated to 10.
