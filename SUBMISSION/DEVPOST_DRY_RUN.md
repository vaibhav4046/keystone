# Keystone - Devpost Dry-Run QA

Paste-ready fields live in `SUBMISSION/STAGE1_ASSETS.md` (Devpost section, 22 fields). This is the
pre-submit checklist. Verified this pass against the live product.

| Check | Result |
|---|---|
| Project title strong | YES - "Keystone - consequence-aware merge governance on the GitLab Orbit graph" |
| Tagline short | YES - one line, "Git review sees files. Production breaks through relationships…" |
| Description not bloated | YES - tight long-description + sectioned fields |
| Best use of GitLab Orbit obvious | YES - dedicated field: reads gl_definition/gl_edge, drives `glab orbit local sql`, proven on a 3rd-party Orbit index |
| Technical implementation credible | YES - deterministic engine, no LLM verdict, 115 tests, cross-checked |
| Live demo link works | YES - https://vaibhav4046.github.io/keystone/ → 200 |
| Render backend link works | YES - https://keystone-zt6c.onrender.com/api/health → 200, LIVE mode |
| GitHub link works | YES - https://github.com/vaibhav4046/keystone → 200 |
| GitLab link works | YES - https://gitlab.com/lalwanivaibhav079/keystone → 200 |
| Video URL | PENDING - the ONLY missing field (placeholder `<paste unlisted URL>` in STAGE1_ASSETS) |
| No placeholder remains except video | YES - every other field is final |
| Limitations honest | YES - FNV-vs-HMAC, self-asserted-vs-OIDC, static call-graph approximation, no live MR webhook |
| Judge verification steps easy | YES - 5-step list (pytest → demo → live route → external repo → README) |

## Submit procedure (when the form is open + video URL exists)
1. Paste fields from STAGE1_ASSETS.md "Devpost" section.
2. Links: live, backend, GitHub, GitLab, video.
3. Confirm zero remaining placeholders.
4. Submit → confirm status reads SUBMITTED → capture the submission URL → I add it to FINAL_10_PACKET.md and push.

## Status
- Completed: all fields + links verified; only the video URL is outstanding.
- Waiting for user login or approval: Devpost sign-in + the video URL (final submit is irreversible and requires the video field).

---

## 2026-06-21 - copy now supports three live claims

The live demo now visibly backs these submission lines: a narrated hands-free
auto-tour (caption HUD), a live "Live backend verified" badge on the deployed
Render engine, and a deterministic Agent fix plan on blocked agent MRs. All
three are CDP-verified on https://vaibhav4046.github.io/keystone/ with zero
console errors.
