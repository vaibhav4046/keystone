# Ship checklist - Keystone

The build is complete and verified end to end on a real GitLab Orbit graph: 83 tests pass / 2
skipped, the engine runs on `~/.orbit/graph.duckdb`, the product drives Orbit's own CLI live, the
precedent contradiction fires on real data, and the hash chain verifies. The static bundle is
deterministic at 495,275 bytes (SHA256 `8B0BAF101705435DEC670690E3C9C01973E3CD2737CF51D11AA68582EE9E43E2`).
What remains needs your credentials or your hands. Each step below is exact and was checked
against this machine.

These are listed because they require sign-in, a payment-free account action, or a screen
recording - things an assistant must not do for you. Do them in order.

## 1. Repository - DONE on GitHub

Already created, public, MIT, pushed, with green CI:

    https://github.com/vaibhav4046/keystone

This is a valid public repo for the Devpost gate. GitHub was used because that is the auth
present on this machine; GitLab had no token, so the GitLab push needs your one-time login.

### Required for this track: also put it on GitLab

This is the GitLab Transcend hackathon, so judges expect a GitLab-hosted repo, a GitLab
pipeline, and ideally a published AI Catalog agent. Treat the GitLab push as required, not
optional. If `glab` is on your PATH, run:

```
glab auth login                 # choose gitlab.com, authenticate in your browser
cd D:\project\keystone
glab repo create keystone --public --source . --remote gitlab --push
```

If `glab` is not installed or not on PATH, the easiest path is to give this session a GitLab
personal access token with `api`, `write_repository`, and `read_api` scopes. Then I can create the
GitLab project, mirror the repo, and publish the AI Catalog agent for you.

The committed `.gitlab-ci.yml` then runs the tests and publishes GitLab Pages automatically.

## 2. Live link - DONE on GitHub Pages

    https://vaibhav4046.github.io/keystone/

Serves the self-contained hero (live-API-first, FALLBACK sample bundle when no backend is
reachable). Judge-clickable, no paid services. If you also push to GitLab, you additionally
get `https://<namespace>.gitlab.io/keystone` from the GitLab pipeline.

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
   The SYMBOLS rail is filtered to callable definitions (functions, methods, classes), so it
   shows real symbols, not file entries. For the cleanest possible rail you can instead index a
   small well-known OSS repo (for example a clone of psf/requests) and pick one of its functions;
   either works, but indexing Keystone itself gives the nice "it reviews its own engine" beat.
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

## 4. Publish the AI Catalog agent (browser, strongly recommended)

In GitLab, publish the Keystone agent to the AI Catalog:

- Agent definition: `.gitlab/agents/keystone/agent.yml`
- Skill interface: `skills/keystone/SKILL.md`
- Runnable proof: `skills/keystone/run_review.py`

Publish with visibility public (no review queue, free for the hackathon). This satisfies the
Showcase Track requirement that at least one agent or flow be published to the AI Catalog and
that it "meaningfully uses GitLab Orbit via its API, CLI, or skill interface" to perform a
specific action rather than chat.

## 5. Devpost submission (after 1-3 are done)

Devpost: gitlab-transcend.devpost.com. Submit at least a day before the deadline
(2026-06-24 14:00 US Eastern). The current submission text is at
`D:\project\keystone\SUBMISSION\DEVPOST.md` and the 3-minute demo script is at
`D:\project\keystone\SUBMISSION\DEMO_SCRIPT.md`. Fill: repo URL (step 1), live link
(step 2), video URL (step 3). After saving, re-open the submission and confirm it reads
SUBMITTED, not DRAFT, and screenshot it. (This is the one that bit the last hackathon.)

## 6. Key rotation

Rotate the four API keys in `.env` (Cerebras, Groq, OpenRouter, Gemini) before or soon after
submission as routine hygiene. `.env` is gitignored and never committed; the governance path
uses no LLM, so the keys are not required for the demo to run.
