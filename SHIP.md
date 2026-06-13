# Ship checklist — Keystone

The build is complete and verified end to end on a real GitLab Orbit graph: 28 tests green,
the engine runs on `~/.orbit/graph.duckdb`, the product drives Orbit's own CLI live, the
precedent contradiction fires on real data, and the hash chain verifies. What remains needs
your credentials or your hands. Each step below is exact and was checked against this machine.

These are listed because they require sign-in, a payment-free account action, or a screen
recording — things an assistant must not do for you. Do them in order.

## 1. Push to GitLab (needs your auth)

glab is already installed. Open a NEW terminal (so glab is on PATH), then:

```
glab auth login                 # choose gitlab.com, authenticate in your browser
cd D:\project\keystone
git branch -M main
glab repo create keystone --public --source . --remote origin --push
```

`glab repo create ... --push` creates the public project and pushes in one step. If the
project already exists, instead run:

```
git remote add origin https://gitlab.com/<your-namespace>/keystone.git
git push -u origin main
```

Verify the repo page shows the files and the visibility is Public.

## 2. Live link (no extra accounts)

The committed `.gitlab-ci.yml` runs the tests on every push and publishes the web hero to
GitLab Pages. After the first push to `main`, watch the pipeline under Build > Pipelines.
When the `pages` job is green, the live link appears under Deploy > Pages, usually:

```
https://<your-namespace>.gitlab.io/keystone
```

That is your judge-clickable link. No Cloudflare, no wrangler, no paid services. (Optional
alternative: `npx wrangler pages deploy web` if you prefer Cloudflare and want to log in.)

## 3. Demo video (under 3 minutes, you record)

Record locally, upload to YouTube as Unlisted, paste the link in Devpost. Devpost does not
embed Loom reliably, so use YouTube. One take, screen plus mic. Shot list:

1. (0:00) One sentence: who it is for and the problem. "A staff engineer is about to approve
   a refactor and needs to see what it actually breaks, with the prior decision in front of
   them, in a record nobody can quietly edit."
2. (0:15) Terminal: index a real repo live, on camera.
   ```
   glab orbit local index D:\project\keystone
   ```
   Point at the JSON: 262 definitions, 689 relationships, database_path ~/.orbit/graph.duckdb.
3. (0:40) Start Keystone on the live graph:
   ```
   $env:KEYSTONE_ORBIT_BINARY = "$env:LOCALAPPDATA\glab-cli\bin\orbit.exe"
   python -m uvicorn backend.app:app --port 8787
   ```
   Open the page. Show the status chips: source LIVE, orbit CLI+DuckDB, chain VERIFIED.
4. (1:05) Pick `compute_blast_radius`. Let the blast radius animate. Say the number out loud:
   12 dependents, computed from the real graph, not estimated.
5. (1:35) The Precedent Panel: the identical-signature CONTRADICTION ("s.castellano rejected
   MR-203 ... needs an RFC first"). This is the beat. "I am about to approve something a
   teammate already rejected for this exact blast radius."
6. (2:05) Type a reason, click APPROVE. The audit ledger appends a row, the chain re-verifies
   green. Then click the tamper demo to show the badge flip red, then self-heal.
7. (2:30) Close: one line on the SKILL (`skills/keystone/SKILL.md`) automating this as a
   GitLab agent workflow, and the MIT repo + live link.

Keep it honest: say "sample fixture" if you ever show the FALLBACK label; never call it live.

## 4. Publish the AI Catalog agent (browser, optional bonus)

In GitLab, publish `skills/keystone/SKILL.md` as a public AI Catalog agent (visibility public,
no review queue, free). This strengthens the "meaningful Orbit use via the skill interface"
gate beyond the in-repo SKILL.md. Your call; the SKILL.md + its runnable `run_review.py` are
already the gate artifact.

## 5. Devpost submission (after 1–3 are done)

Devpost: gitlab-transcend.devpost.com. Submit at least a day before the deadline
(2026-06-24 14:00 US Eastern). The organic draft is at
`D:\project\keystone-plan\KEYSTONE_DEVPOST_SUBMISSION.md`. Fill: repo URL (step 1), live link
(step 2), video URL (step 3). After saving, re-open the submission and confirm it reads
SUBMITTED, not DRAFT, and screenshot it. (This is the one that bit the last hackathon.)

## 6. After the hackathon

Rotate the four API keys in `.env` (Cerebras, Groq, OpenRouter, Gemini). They were pasted in
chat during setup, so treat them as exposed and regenerate them once judging is done.
