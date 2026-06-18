# Keystone - 3-minute demo script

Record your screen + voice. Upload to YouTube as Unlisted and paste the URL into Devpost.
Keep it under 3 minutes. Do not call fallback data "live."

---

## Setup (before you hit record)

1. Open two terminals side by side:
   - Terminal A: Keystone backend
   - Terminal B: orbit CLI
2. Open the live demo in a browser: https://vaibhav4046.github.io/keystone/
3. Start the backend on the real graph:

```powershell
$env:KEYSTONE_ORBIT_BINARY = "$env:LOCALAPPDATA\glab-cli\bin\orbit.exe"
cd D:\project\keystone
python -m uvicorn backend.app:app --port 8787
```

Wait for the startup log to show `Orbit CLI verified`, `graph rows=262`, `edges=689`, and `symbols=120`.

---

## Shot list & narration

### 0:00-0:15 — The problem in one sentence

**Visual:** Browser on the Keystone hero page, terminal visible in background.

**Narration:**
"A staff engineer is about to approve a refactor. Git says no conflict, but the call graph says
this function is under twelve dependents. I built Keystone to surface what the normal review page
cannot see, and to refuse approvals that contradict the record."

Click the primary CTA: **Open reviewer cockpit**.

---

### 0:15-0:35 — The graph is real

**Visual:** Status panel at the top of the cockpit.

**Narration:**
"The status panel tells the truth. Source is live. Orbit access is CLI-verified. The graph is this
very repo: 262 definitions, 689 relationships, 120 verified symbols. This is not a mock."

Point at each status chip as you say it.

---

### 0:35-0:55 — Blast radius

**Visual:** Symbol selector or the default view; click `compute_blast_radius`.

**Narration:**
"Pick a symbol. Keystone computes its bounded reverse blast radius from the real Orbit graph: 12
direct callers. The concentric rings show scope and severity. The number is deterministic, not
estimated."

Let the ring animation finish.

---

### 0:55-1:20 — The contradiction

**Visual:** Precedent panel, showing the seeded contradiction for `compute_blast_radius`.

**Narration:**
"This is the beat. A teammate already rejected this exact blast signature in MR-203. Keystone
matches by signature and blocks me from approving the same change without an accountable override."

Scroll to the precedent row and highlight `contradiction_strength: identical`.

---

### 1:20-1:45 — Policy tier and governance action

**Visual:** Policy / gate panel, showing the computed tier and ALLOW/HOLD/BLOCK.

**Narration:**
"The blast radius maps to a policy tier written as code. Cross-team scope means two approvers and
a 24-hour review window. The action is ALLOW, but the precedent contradiction turns the effective
gate into a BLOCK until I check the override box."

Check the override box, type a reviewer ID, and type a reason.

---

### 1:45-2:10 — Decision and tamper-evident ledger

**Visual:** Click **Record approval**. Scroll to the audit ledger.

**Narration:**
"Every decision is appended to an HMAC-keyed, hash-chained ledger. The chain verifies green. If
someone edits a row, the badge flips red and the verifier catches it. Let me show the tamper demo
— edit a row, the chain breaks, then it self-heals when the row is restored."

Trigger the tamper demo, watch the badge flip red, then restore and watch it go green.

---

### 2:10-2:30 — Cross-MR collisions and merge order

**Visual:** Collisions panel / merge-order section.

**Narration:**
"Keystone also scans open merge requests for blast-radius collisions that Git cannot detect. It
finds seven collision pairs in this fixture and computes a safe merge order. If a cycle exists,
it reports the MRs that cannot safely merge together."

Point at the merge-order list and one collision pair.

---

### 2:30-2:50 — AI agent, catalog, and close

**Visual:** Switch to the repo README or the `skills/keystone/SKILL.md` file.

**Narration:**
"There is an AI layer, but it is intentionally off the trust path. The agent calls deterministic
tools for blast radius, precedent, and reviewers, then recommends. The model proposes; the engine
decides. The same workflow is packaged as a GitLab AI Catalog agent."

Show `.gitlab/agents/keystone/agent.yml` briefly.

**Narration:**
"Keystone: deterministic governance on top of the GitLab Orbit graph. MIT repo, live demo, and
this video are in the Devpost entry."

---

## End card

Show on screen for 3 seconds:

- Repo: https://github.com/vaibhav4046/keystone
- Live demo: https://vaibhav4046.github.io/keystone/
- Devpost: gitlab-transcend.devpost.com

---

## Recording tips

- Use OBS or similar, 1920x1080, capture browser + mic only.
- If the backend is not running, the page switches to the committed SNAPSHOT. Say so out loud; do
  not call it live.
- Keep mouse movements slow and deliberate.
- Pause narration briefly after clicking so the UI finishes animating.
