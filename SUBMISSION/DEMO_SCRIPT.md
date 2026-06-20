# Keystone — 3-minute demo script (canonical)

This is the ONLY demo script. It shows the real skill workflow producing a real result, not a
website tour. Record screen + voice, upload public/unlisted, paste the URL into Devpost. Under 3:00.

Pre-record setup (one terminal, repo root):
```
cd D:\project\keystone
```
The skill runs server-less against the committed real Orbit index, so nothing else needs starting.

---

## 0:00–0:15 — The pain (terminal + one sentence)

Show two file paths changing in a diff (e.g. `core/impact.py` and `core/audit.py`).

Say: "These two merge requests touch different files. Git reports no conflict. They still break
production together, because both change a function the same downstream code depends on."

## 0:15–0:30 — The killer workflow (one sentence)

Say: "Keystone uses the GitLab Orbit code graph to investigate change impact, find precedent,
detect risk, produce a decision, and verify that decision in a tamper-evident ledger. Here it is
as a skill, running for real."

## 0:30–1:35 — The real skill, producing a real result (THE core)

Type and run, on camera:
```
python skills/keystone/run_review.py compute_blast_radius --local
```
Point at the actual output as it prints:
- `blast radius : ring1=12 ... affected=12` — "Twelve definitions depend on this symbol. Computed
  from the real Orbit graph, not estimated."
- `precedent : 3 matches approved=1 rejected=2`
- `CONTRADICTION (identical-signature): Antigravity rejected ... "Requires migration tests first"`
  — "This exact blast signature was already rejected. Keystone surfaces it."
- `chain : VERIFIED`

Then run the enforceable gate:
```
python skills/keystone/run_review.py compute_blast_radius --local --fail-on-block
```
Point at: `GATE BLOCKED (GOVERNANCE_BLOCK): compute_blast_radius is refused by policy.`
Say: "Non-zero exit. Dropped into CI, this fails the pipeline. The skill does work; it does not chat."

## 1:35–2:05 — The Orbit graph is the source (evidence)

Say: "Every number came from a real GitLab Orbit index." Show one of:
```
"$LOCALAPPDATA\glab-cli\bin\orbit.exe" sql "SELECT count(*) FROM gl_edge WHERE relationship_kind='CALLS'"
```
or open the live site, click **Demo on pallets/click**: "This is a real Orbit index of pallets/click
— 1,841 definitions. Keystone flags Context colliding with HelpFormatter across core.py and
formatting.py, and ranks Context an 81-dependent single point of failure." (Recognizable, not a toy.)

## 2:05–2:30 — Decision, block, verified output

On the live site Audit Ledger: click **Simulate tamper** — "Edit a past decision and every hash
after it recomputes: the chain goes BROKEN." Click **Restore chain** — "Restore, it re-verifies.
You cannot quietly rewrite an approval."

## 2:30–2:50 — Why developers care

Say: "AI agents now author merge requests faster than anyone can review them. Keystone runs every
human and agent change through the same Orbit-graph gate — ALLOW, HOLD, or BLOCK — and refuses an
approval that contradicts a recorded rejection. It is packaged as a GitLab AI Catalog agent
(.gitlab/agents/keystone/agent.yml) and a CI gate."

## 2:50–3:00 — One-sentence close

Say: "Keystone: deterministic, auditable change governance on the GitLab Orbit graph. The model
proposes; the engine decides; the ledger remembers."

End card (3s):
- GitLab repo: https://gitlab.com/<YOUR_USERNAME>/keystone
- AI Catalog: <paste artifact link>
- Live demo: https://vaibhav4046.github.io/keystone/

---

Honesty rules while recording:
- Do not call the committed snapshot "live" unless the backend status panel says LIVE.
- The in-browser ledger hash is a fast FNV demo of the mechanism; production uses HMAC-SHA256.
- The 120/120 Orbit cross-check is a build-time artifact ("we ran"), not a query running on the page.
