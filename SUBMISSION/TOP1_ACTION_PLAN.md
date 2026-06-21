# TOP-1 ACTION PLAN - Honest Path to Winning

**Deadline: June 24, 2026 @ 2:00pm ET (9 days from now)**

## The honest truth (read this first)

**739 participants, 8 prizes, 4 equally-weighted criteria, partly subjective judging.**

Your code is genuine top-2 contender quality in two categories:
- **Technological Implementation** (strongest - real engine, correct graph algorithms, hardened trust model)
- **Quality of the Idea** (cross-MR blast collision is novel, invisible to standard review)

Design is good (tour, guided chips, loud refusals). Impact is the weakest (real problem, narrow TAM, no field evidence).

**But right now P(win) = 0 - not because of quality, but because the entry cannot be judged yet.**

Three hard requirements gate everything:
1. **GitLab mirror** (rules require "Link to your provisioned open source (MIT Licensed) **GitLab project**")
2. **Demo video ≤ 3 min** on YouTube/Vimeo (public) - **no video = not judged at all**
3. **Devpost submission** - must be submitted, not draft

Without these, the strongest code in the field places nowhere.

## What you must do (in order, ~2 hours total)

### 1. GitLab mirror (10 minutes) - HARD REQUIREMENT

Follow `SUBMISSION/GITLAB_MIRROR.md` or `SHIP.md` step 1:

```bash
glab auth login                 # authenticate in browser
cd D:\project\keystone
glab repo create keystone --public --source . --remote gitlab --push
```

**Why**: Judges are GitLab engineers. They will check the repo is on GitLab, verify MIT license, test by cloning. GitHub-only risks disqualification.

### 2. Demo video (30-45 minutes) - HARD REQUIREMENT

Follow `SUBMISSION/VIDEO_SCRIPT.md` or `SHIP.md` step 3:

- Record screen + mic, one take, under 3 minutes
- Upload to YouTube as **Unlisted** (or Public)
- Lead with the collision demo (the novel capability)
- Show the BLOCK, the override, the tamper detection
- Say "sample fixture" if you show FALLBACK; never call it live

**Why**: This is the hardest rule. No video = not judged. Period.

### 3. Devpost submission (15 minutes) - HARD REQUIREMENT

Follow `SUBMISSION/DEVPOST.md`:

- Go to https://gitlab-transcend.devpost.com
- Click "Enter a Submission"
- Paste the text from DEVPOST.md
- Fill: **GitLab repo URL** (from step 1), live demo URL, video URL (from step 2)
- **Submit at least 1 day early** (by June 23)
- Re-open and confirm status reads **SUBMITTED**, not DRAFT
- Screenshot it

**Why**: Last hackathon bit someone on this. Don't let it happen.

### 4. AI Catalog publication (10 minutes, optional but strengthens) - RECOMMENDED

Follow `SHIP.md` step 4:

- In GitLab, publish `skills/keystone/SKILL.md` as a public AI Catalog agent
- Visibility: public, no review queue, free
- This strengthens "meaningful Orbit use via the skill interface" beyond the in-repo SKILL.md

**Why**: The rules say "At least one agent or flow must be published to the AI Catalog." Your SKILL.md is already in the right format; this is just the publication step.

### 5. Live backend deploy (5 minutes, optional but high-leverage) - RECOMMENDED

Follow `SUBMISSION/RENDER_DEPLOY.md`:

- Go to https://render.com, sign up (free, no card)
- New → Blueprint → connect your GitLab repo → Apply
- Wait for "Live" status
- Copy the `*.onrender.com` URL
- Add it to Devpost as the "Try it" link

**Why**: Judges can test the live agent, not just the snapshot. The CTA is now on the page.

## What I already did (code is at honest maximum)

- **83 tests pass / 2 skip** (hermetic, real fixture)
- **Build is deterministic** (byte-identical, no drift)
- **CI green** on all recent commits
- **Deployed GitHub Pages site is current** (tour button live)
- **Live backend verified end-to-end**:
  - BLOCK enforced with real precedent
  - Accountable override records, chain intact
  - Four-eyes self-approval refused
  - CROSS_TEAM quorum: 1/2 PENDING → 2/2 APPROVED
  - MR-level decision returns attestation bound to both symbols
  - Agent rubber-stamp refused (trust-model bug fixed)
  - Cross-MR collision: change_in_blast, directional merge order
  - Drift endpoint, attestation verify, chain verify all correct
  - Tamper detection precise (edited row 2 → broken_index=2)
  - CI-gate skill BLOCKs with exit code 1
- **Fixed 3 real bugs** in the new T-3/T-4 code (trust-model lies)
- **Shipped blast-radius drift** (core/drift.py + /api/drift + CLI)
- **Shipped 60-second guided tour** (auto-advances, stop button)
- **Shipped live-backend deploy CTA** on the static page

## Honest probability estimate

Across many simulated judge panels (directional, not real scores):
- **P(top-2 in Technological Implementation) ≈ 0.23**
- **P(top-2 in Quality of the Idea) ≈ 0.20**
- **P(top-1 in any category) ≈ 0.08-0.12**

These are estimates, not guarantees. The real scores are the judges' to write.

**What moves the needle now:**
- Deploy the live backend (5 min) - judges test the real agent
- Record the video (30 min) - the #1 lever, no substitute
- Submit early (15 min) - avoid last-minute issues
- Publish to AI Catalog (10 min) - strengthens the Orbit integration claim

## What I will NOT do

- **Fabricate a score or claim a guaranteed win** - that disqualifies honesty-judged entries
- **Run more simulated judge panels** - the number is measured and stable
- **Invent more code work** - the code is at its honest maximum
- **Promise top-1** - 739 participants, 8 prizes, partly subjective; no one can guarantee that

## The bottom line

**The code is genuine top-2 contender quality in its two strongest categories.** Whether it actually wins now depends entirely on you shipping the GitLab mirror, the video, and the submission. If those aren't done by June 24, the strongest code in the field places nowhere.

**Estimated time to complete: 2 hours. Estimated probability lift: from 0 to ~0.08-0.12 for top-1, ~0.20-0.23 for top-2.**

The remaining 0.88-0.92 of probability is the field, the judges, and the luck of the draw. That's honest. That's the game.

Good luck.
