# Keystone — submission checklist (P0 first)

Deadline: 2026-06-24 14:00 ET. Two-stage judging: Stage 1 is PASS/FAIL on the items marked [P0].
A perfect Stage-2 score is worthless if any [P0] is open.

## P0 — eligibility (close ALL before anything else)

| # | Requirement | Status | Owner |
|---|---|---|---|
| 1 | MIT license in repo | DONE (`LICENSE`, MIT) | — |
| 2 | Working skill/agent that does real automation (not chat) | DONE — `run_review.py --local` verified producing report + BLOCK | — |
| 3 | Meaningfully uses GitLab Orbit | DONE — reads `gl_definition`/`gl_edge`, drives `glab orbit local sql`; real index of this repo + pallets/click | — |
| 4 | Duo Agent Platform agent definition exists | DONE — `.gitlab/agents/keystone/agent.yml` (schema match to Catalog = UNVERIFIED, validate on publish) | — |
| 5 | GitLab repo public + current (99 commits behind) | OPEN | YOU (needs token) |
| 6 | Published to the AI Catalog | OPEN | YOU (GitLab account/UI) |
| 7 | Public demo video < 3 min | OPEN | YOU (record from DEMO_SCRIPT.md) |
| 8 | Devpost links GitLab repo + Catalog + video | OPEN (placeholders set) | YOU (paste links) |

## Exact commands YOU must run

1) Rotate a fresh GitLab Personal Access Token (the old one was scrubbed), create a public project
   `keystone` on gitlab.com (MIT, no README), then push 99 commits:
```
cd D:\project\keystone
git remote set-url gitlab https://oauth2:<NEW_GITLAB_TOKEN>@gitlab.com/<YOUR_USERNAME>/keystone.git
git push gitlab main
git remote set-url gitlab https://gitlab.com/<YOUR_USERNAME>/keystone.git
```
   Verify: open `https://gitlab.com/<YOUR_USERNAME>/keystone` — public, MIT visible, latest commit
   matches `git rev-parse --short HEAD`.

2) Publish to the AI Catalog: in GitLab, open the Duo Agent Platform / AI Catalog, add the agent
   from `.gitlab/agents/keystone/agent.yml`, set visibility public. Copy the Catalog artifact URL.
   (UNVERIFIED: if the Catalog rejects the YAML schema, adjust to its required format — the workflow
   logic does not change.)

3) Record the video using `SUBMISSION/DEMO_SCRIPT.md` (CLI workflow first, not a website tour).
   Upload public/unlisted. Copy the URL.

## Links YOU must paste into Devpost (and into DEVPOST.md header)

- GitLab repo: `https://gitlab.com/<YOUR_USERNAME>/keystone`
- AI Catalog artifact: `<from step 2>`
- Video: `<from step 3>`
- Live demo: `https://vaibhav4046.github.io/keystone/`

## Stage-2 quality (already in good shape; do AFTER P0)
- Data-driven dashboard, real hash chain, honest CTA, inspectable collisions, two real Orbit demos.
- README quick-start + verification command present. Run `pytest -q` and the skill once on camera.

## One-line verification a judge can run
```
python skills/keystone/run_review.py compute_blast_radius --local --fail-on-block
```
Expect a governed-review report, an identical-signature CONTRADICTION, and `GATE BLOCKED` (non-zero).
