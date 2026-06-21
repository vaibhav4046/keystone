# Keystone - Final 10/10 Judge Packet

One page to evaluate, verify, and submit Keystone. Every number is real and reproducible.
Full paste-ready submission copy (Devpost 22 fields, AI Catalog, video script) lives in
`SUBMISSION/STAGE1_ASSETS.md`; this packet is the judge-facing summary + the impact proof + the
exact submit checklist.

## Links
- **Live demo:** https://vaibhav4046.github.io/keystone/
- **Backend (Render, LIVE):** https://keystone-zt6c.onrender.com  (`/api/health` → ok; free instance, first hit after idle may take ~50s to wake)
- **GitHub:** https://github.com/vaibhav4046/keystone
- **GitLab (primary):** https://gitlab.com/lalwanivaibhav079/keystone
- **Video:** `<paste unlisted YouTube/Vimeo URL>`
- **Commit:** `dd86d9b` · **Track:** GitLab Transcend - Showcase · **License:** MIT

## One-command demo
```bash
pip install -r requirements.txt
python skills/keystone/run_review.py demo
```
**Expected CLI outputs**
```
python -m pytest -q                                                     -> 115 passed, 2 skipped
python skills/keystone/run_review.py demo                               -> exit 0  (all 6 beats below)
python skills/keystone/run_review.py shadow-merge                       -> VERDICT: BLOCK   (exit 2; change_in_blast)
python skills/keystone/run_review.py shadow-merge --safe                -> VERDICT: ALLOW   (exit 0)
python skills/keystone/run_review.py memory-gate compute_blast_radius --prove
                                                                        -> OVERRIDES the agent's APPROVE (exit 2)
python skills/keystone/run_review.py shadow-merge --graph data/click_graph.duckdb --a echo --b make_context
                                                                        -> VERDICT: BLOCK on pallets/click (exit 2)
```

## 90-second judge route (no terminal)
1. Open the live demo. Read the hero: two safe MRs break together; Git sees files, Orbit sees the call graph, Keystone vetoes and logs it.
2. Click **Try the live demo** -> green **REAL GitLab Orbit graph** badge -> the silent collision (`compute_blast_radius x verify`, 5 shared dependents).
3. Open **Reviewer Cockpit** (judge-demo panel link) -> the blast-radius graph renders.
4. Open **Audit Ledger** (judge-demo / verify-panel link) -> click **Simulate tamper** -> the hash chain breaks -> **Restore** re-validates.
5. Click **pallets/click** (verify panel) -> the same engine on a 1,841-definition third-party library.

## 3-minute technical verification route
1. `python -m pytest -q` -> 115 passed, 2 skipped.
2. `python skills/keystone/run_review.py demo` -> BLOCK / ALLOW / AI override / ledger break, in one command.
3. `python skills/keystone/run_review.py shadow-merge --graph data/click_graph.duckdb --a Context --b echo` -> real collision on a repo we didn't write (`tests/test_external_repo.py` enforces it).
4. README -> **"How to verify this is real"** maps every claim to a check; the engine cross-checks 120/120 ring-1 counts against Orbit's own `glab orbit local sql`.

## Impact proof (concrete, no hype)
AI coding agents now increase merge velocity - more parallel MRs than any reviewer can hold in their head. Git's conflict check is textual: it only catches two changes to the **same lines**. The dangerous modern failure is two changes to **different files** that break together because they share a runtime dependency. A human reviewer cannot manually reason over the whole call graph; GitLab Orbit is the layer that exposes that relationship graph. Keystone turns it into a deterministic **pre-merge gate**, so the payoff is fewer semantic production incidents - and the value compounds with every agent added to the pipeline.

**The scenario, proven in the demo:** MR A changes `compute_blast_radius`. MR B changes `verify`. Git sees different files and no conflict; both pass review. Orbit shows they share runtime dependents. Keystone blocks the merge, returns a safe merge order, and writes the decision to a tamper-evident ledger. The same engine reproduces real collisions on pallets/click - so it generalises beyond our own code.

## Security and honesty notes (a security judge can trust these)
- **No LLM on the decision path.** The verdict is a deterministic graph computation; the optional AI assistant only explains.
- **Numbers are observed**, cross-checked against `glab orbit local sql` (120/120 match); an independent raw-SQL recompute is asserted in tests.
- **Ledger:** HMAC-SHA256 hash-chained in production; the static browser demo uses a published FNV-1a key to show the mechanism (tamper-**evident**, not tamper-proof; no insider resistance) - stated in the UI badge.
- **Identity:** self-asserted in the static demo; GitLab OIDC-bound (RS256/JWKS) on the CI path - labelled.
- **CSP** on both static entries (console strict / no-eval; landing scoped to `unsafe-eval`, handles no decisions) + backend header; CDN scripts pinned with SRI.

## Known limitations (stated, not hidden)
- Blast radius is a static call-graph approximation (Python dynamic dispatch under-approximated; 120/262 self-graph symbols CLI-cross-verified).
- Published-key static ledger proves no accidental corruption, not insider tampering.
- Content-addressed precedent reduces rename/re-index evasion but a full epicenter rename + dependent-set restructure can still alter the key.
- No live MR webhook yet (CLI/CI gate today).

## Why it should win
1. A capability nothing else shows: cross-MR silent collision + safe merge order on the Orbit graph.
2. Deepest, most honest Orbit use; proven general on a third-party repo.
3. Deterministic, no-LLM verdict; 115 tests; one-command reproducible.
4. Trust as a feature: tamper-evident ledger you watch break, labelled honesty.
5. First 90 seconds is engineered and live: one CTA, judge-demo + verify panels, working graph, zero console errors.

## Why it could lose + mitigation
| Risk | Mitigation |
|---|---|
| Impact reads niche (TAM) | Impact proof above + agent-scale thesis; a real partner metric is the only external lift |
| No video / not submitted | Submit checklist below + full script in STAGE1_ASSETS.md |
| Judge wants live `orbit sql` on the decision path | Cross-check is live per-session; full webhook is the documented next step |
| Remote judge hits static snapshot | Render one-click steps below (backend proven deploy-ready) |

## Render deploy (exact)
1. render.com -> sign in. 2. **New +** -> **Blueprint**. 3. Connect GitHub -> pick `vaibhav4046/keystone`. 4. It detects `render.yaml` (service `keystone`, Docker, free). 5. **Apply** -> wait for **Live**. 6. Copy the URL.
- Env (preset by render.yaml): `KEYSTONE_GRAPH_PATH=data/keystone_self_graph.duckdb`, `KEYSTONE_PREFER_LIVE=1`; optional secret `OPENROUTER_API_KEY`.
- Health: `curl -s https://<url>/api/health` -> `{"ok":true,...}`; `curl -sI https://<url>/ | grep -i content-security-policy`.
- Failure recovery: redeploy from the Render dashboard; or the static GitHub Pages demo is fully self-contained; or `fly deploy` (fly.toml present).
- Devpost paste once deployed: *"Live backend (real agent + live orbit sql cross-check): https://<url> - health: /api/health."*

## Final submit checklist (each line is one action)
```
[ ] 1. (optional) Render: New+ -> Blueprint -> vaibhav4046/keystone -> Apply -> copy URL -> curl /api/health
[ ] 2. Record the 2:30 video (script: SUBMISSION/STAGE1_ASSETS.md) -> upload YouTube/Vimeo UNLISTED -> copy URL
[ ] 3. Devpost: paste the 22 fields (STAGE1_ASSETS.md) + repo links + video URL -> Submit -> confirm SUBMITTED -> screenshot
[ ] 4. AI Catalog: GitLab sign-in -> publish Public agent -> paste the AI Catalog copy (STAGE1_ASSETS.md)
[ ] 5. Post-submit: reopen Devpost, confirm status SUBMITTED, links resolve, video plays
[ ] 6. Post-hackathon: rotate the four .env keys
```

---

## 2026-06-21 - winner-mode session additions (live + verified)

Three high-impact additions shipped and verified on the live deploy
(https://vaibhav4046.github.io/keystone/), GitHub + GitLab at the same HEAD,
CI green (run 27893658209):

1. **Visible guided-demo caption HUD.** "Watch it run" now drives a fixed
   bottom-center AUTO-DEMO banner that narrates each of the 6 steps, shows live
   step-progress dots, and has an EXIT control. Previously the caption was set in
   state but never rendered. CDP-verified live: HUD shows, captions advance
   ("Two safe-looking MRs..." -> "Blast-radius graph..."), EXIT dismisses, zero
   console errors.

2. **Live backend status badge.** The landing probes the deployed Render engine
   (/api/status) on mount and shows an honest pill: green "Live backend verified"
   (with source mode + 262 indexed defs + chain state in the tooltip) when it
   answers, or "Backend asleep, snapshot live" on a cold free-tier start. Hard 9s
   timeout + catch means a sleeping backend never blocks the page. CDP-verified
   live: badge reads "Live backend verified". Directly answers the "feels static"
   critique - the live engine is now visibly reachable.

3. **Agent fix plan.** The Engineering Harness now surfaces a deterministic
   remediation card on a blocked bot MR: why it was blocked (the shared
   dependents), a 4-step ordered plan (stack the MRs, add an integration test over
   both symbols, merge in the topological safe order, re-run shadow-merge + memory
   gate + record to the ledger), and the agent status. An "ADVISORY - GATE IS
   DETERMINISTIC" chip keeps the honesty line. CDP-verified live: card present, all
   4 steps render.

Also: stripped all 52 em/en dashes the recent redesign reintroduced into the
landing copy, back to the repo's hyphen convention.

Tests: 115 passed / 2 skipped. CLI: demo / shadow-merge / shadow-merge --safe /
memory-gate --prove / external pallets-click graph all exit with the right codes.
