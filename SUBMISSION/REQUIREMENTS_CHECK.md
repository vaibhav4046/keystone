# Keystone - Hackathon Requirements Check

GitLab Transcend Hackathon, Showcase track (gitlab-transcend.devpost.com).
Deadline: 2026-06-24 14:00 US Eastern. Win model: top-2 in any ONE of four
equally-weighted categories (Technological Implementation, Design & Usability,
Potential Impact, Quality of the Idea). 1st = $2k, 2nd = $1k per category.

Statuses used: **Completed** / **Waiting for user login or approval** /
**Impossible due to external judge control**.

Last verified: 2026-06-21 (this session), against the live deploy and CI.

| # | Requirement | Status | Evidence | Remaining / blocker |
|---|-------------|--------|----------|---------------------|
| 1 | Public source repository | Completed | github.com/vaibhav4046/keystone (public) + gitlab.com/lalwanivaibhav079/keystone, both at the same HEAD, pushed this session | none |
| 2 | OSI license at repo root | Completed | MIT `LICENSE` committed | none |
| 3 | Working live demo | Completed | https://vaibhav4046.github.io/keystone/ returns 200; CDP break-test passes (tamper/restore, cockpit 17/17, dynamic pallets load, zero console errors, no overflow 320-1440px) | none |
| 4 | Deployed backend (optional but allowed) | Completed | https://keystone-zt6c.onrender.com/api/health `{"ok":true}`; /api/status source_mode LIVE, 262 defs, audit chain ok; CORS allow-lists the Pages origin; landing shows a live "Live backend verified" badge | none |
| 5 | Meaningful Orbit use via API/CLI/skill | Completed | Product reads a real `orbit index` DuckDB (gl_definition/gl_edge...); `skills/keystone/SKILL.md` + `run_review.py` drive the engine; external-graph proof on pallets/click (`shadow-merge --graph data/click_graph.duckdb`) | none |
| 6 | README with verification steps | Completed | README leads with the one-command demo (`python skills/keystone/run_review.py demo`), "how to verify this is real" table, integrity model, limitations | none |
| 7 | Tests / CI green | Completed | 115 passed / 2 skipped (`pytest -q`); GitHub Actions CI green incl. data.json drift check + Pages deploy (run 27893658209) | none |
| 8 | <3min demo video (HARD submission gate) | Waiting for user login or approval | Full 2:30 shot-by-shot script + 60s cut in `SUBMISSION/VIDEO_FINAL_READY.md`; one-command `demo` beat is recorded-ready | Cannot screen/voice record from this environment; user records + uploads unlisted to YouTube |
| 9 | Devpost submission (text fields + links) | Waiting for user login or approval | Paste-ready fields in `SUBMISSION/DEVPOST.md` + `STAGE1_ASSETS.md` | Needs Devpost sign-in, T&C, irreversible submit (and the video URL first) |
| 10 | AI Catalog entry (bonus / track fit) | Waiting for user login or approval | Paste-ready copy in `SUBMISSION/AI_CATALOG_DRY_RUN.md` | Needs GitLab browser sign-in to publish |
| 11 | AI-generated-content disclosure (if required) | Completed | README + UI state plainly: deterministic gate, no LLM on the verdict path; the optional NL brief is labelled "AI - provider" vs "deterministic summary" | none |
| 12 | Runs from GitLab (not just GitHub) | Completed | GitLab mirror at the same HEAD; `.gitlab-ci.yml` runs tests + (optionally) Pages | none |
| 13 | Screenshots / tags / team details | Waiting for user login or approval | Committed stills in `_shots/`; tags/team are Devpost form fields | Filled at Devpost submit time |
| 14 | External APIs / deployed backend allowed | Completed | Rules permit deployed services; backend is free-tier Render, demo degrades gracefully to the committed snapshot when cold | none |

## Summary

- **14 requirements. 9 Completed. 5 Waiting for user login or approval.** Zero
  "Impossible due to external judge control".
- The 5 waiting items collapse to **three real human actions**: record the video
  (hard gate), submit on Devpost, publish the AI Catalog entry. All three need
  logins this environment does not hold; everything around them is paste-ready.
- No requirement is blocked by code. The product, live demo, backend, repos
  (both remotes), CI, license, README, and skill artifact are all in place and
  re-verified this session.
