# Keystone demo video script (target 2:25, hard cap 3:00)

The single hardest submission gate: no video means the entry is not judged at all. This is a
shot-by-shot script you can record in one take by clicking exactly what is written. Every
number on screen is real and computed from a real `orbit index` of this repo, so nothing here
is staged or faked.

## Before you record

- Best: deploy the live backend first (one click: render.com to New to Blueprint to this repo
  to Apply, uses the committed `render.yaml`). Record against the live URL so the AI assistant
  runs a fresh tool loop on camera and the status badge reads `LIVE`. This directly answers the
  judges' "I only saw a static snapshot" objection.
- Fallback that still works: record against https://vaibhav4046.github.io/keystone/ . Everything
  in the spine below runs client-side on the static deploy (the collision detector recomputes in
  the browser, the gate is interactive, the AI panel shows a real recorded run). The only
  difference is the status badge reads `SNAPSHOT` instead of `LIVE`.
- Screen at 1920x1080, browser zoom 100 percent, close other tabs. Record at 30fps.
- Do one silent dry run clicking the path end to end so the take is smooth.
- Keep your voice flat and factual. The product is the show. No hype words.

## The spine (say this in one sentence before you start, to yourself)

Two merge requests both passed review and still broke together. Keystone names the collision and
the safe merge order, then the gate refuses the change that contradicts a prior rejection, and
leaves a record nobody can quietly edit.

## Beat-by-beat map to the four judging criteria

The four criteria are equally weighted, and a win is top-2 in one category. The script is built so
every beat scores a criterion and the two strongest categories (Technological Implementation and
Quality of the Idea) are hit hardest. Keep this in your head while recording; it is why each beat
is where it is.

| time | beat | primary criterion it scores | also scores |
|------|------|-----------------------------|-------------|
| 0:00-0:18 | the 2am-break hook | Potential Impact (the real pain) | Quality of the Idea |
| 0:18-1:05 | cross-MR collision + safe merge order | **Quality of the Idea** (the new capability) | Technological Implementation |
| 0:51 | add a live MR, watch it recompute | Design & Usability (interactive, no backend) | Tech |
| 1:05-1:18 | review-debt hazard | Quality of the Idea (second hazard) | Tech |
| 1:18-1:40 | blast radius + the `orbit sql` badge | **Technological Implementation** (meaningful Orbit, checkable) | Impact |
| 1:40-1:58 | precedent contradiction + the BLOCK | Quality of the Idea (binding precedent) | Tech |
| 1:58-2:18 | the bounded AI agent, off the trust path | **Technological Implementation** (real working AI) | Quality of the Idea |
| 2:18-2:38 | hash-chained ledger + attestation | Technological Implementation (tamper-evident) | Impact |
| 2:38-2:50 | close: Orbit-native, the wedge | Tech + Impact | Design |

If a judge watches only the first 45 seconds, they must come away with the one-line idea
("two MRs broke together and nothing but the call graph could see it") and see it recompute live.
That is the single most important stretch of the video. Everything after it is proof.

---

## 0:00 to 0:18  Hook (screen: the hazard X-ray section at the top of the page)

ON SCREEN: the page already open, scrolled to the CROSS-MR BLAST COLLISION panel.

SAY:
"Two engineers open two merge requests. Different files. No merge conflict. Both pass review.
They merge, and production breaks, because one of them changed a function the other one quietly
depended on. Git can't see that. The review can't see that. The call graph can."

## 0:18 to 1:05  The novel capability: cross-MR collision + safe merge order

ON SCREEN: point the cursor at the three demo MRs (MR-204, MR-207, MR-211), then at the red collision rows.

SAY:
"Keystone reads the GitLab Orbit code graph and finds it. MR-204 speeds up the blast engine.
MR-207 tunes the impact API, a different file, no text conflict, and it calls exactly what 204
is changing. Keystone flags the collision, marks that Git sees no conflict, and shows the shared
symbols. Then it computes a safe merge order with a topological sort: merge 204 first, then 207,
so the dependent is re-reviewed against the change it relies on. If the merges formed a cycle it
would say so instead, coordinate these, do not order them."

ACTION (do this on camera, slowly): click the "add a symbol as an open MR" box, type `verify`,
press Enter.

SAY:
"And it is live. I add a third open merge request, and the collisions and the merge order
recompute in the browser on the spot. This is a deterministic graph computation, not a model
guessing."

## 1:05 to 1:18  Second hazard: review debt

ON SCREEN: scroll a little to the REVIEW DEBT list.

SAY:
"Same idea, second hazard. These are high-blast-radius symbols that no test file directly
exercises. High impact, and unverified. The graph can rank exactly those."

## 1:18 to 1:58  Govern the change: blast radius, precedent, the BLOCK

ACTION: in the SYMBOLS list click `compute_blast_radius`.

SAY (while the impact rings draw):
"Now I am the reviewer about to approve a change to this symbol. Keystone shows the real blast
radius, twelve dependents, ranked in rings out from the change. Next to it is the exact `orbit
sql` command that produced that count, so the number is checkable, not asserted."

ACTION: point at the PRECEDENT panel, then the GOVERNANCE panel showing BLOCK.

SAY:
"This change has the same blast signature as a change that was rejected before. Keystone surfaces
that contradiction at the moment of approval, maps the blast radius to the CROSS-TEAM tier, and
the gate refuses the approval. You cannot quietly re-approve what was already rejected without a
recorded, accountable override."

ACTION: try to click APPROVE to show it is disabled / returns the BLOCK, then leave it.

## 1:58 to 2:18  The AI that is allowed nowhere near the verdict

ON SCREEN: the AI ASSISTANT panel with its tool trace.

SAY:
"There is a real AI agent here, and this is the part I care about most. It runs a bounded loop:
it calls the deterministic engine for the blast radius, the precedent, the suggested reviewers,
and then it recommends a next step. You can see the exact tools it called. It never produces a
number and it never records a decision. The model proposes. The deterministic gate decides. That
boundary is the whole point."

## 2:18 to 2:38  The record nobody can edit

ON SCREEN: the AUDIT LEDGER with the chain-verified badge; click the tamper button if you want
the red break to show, then re-verify.

SAY:
"Every decision is appended to a hash-chained, HMAC-keyed ledger. Recompute it and you get a
green verified badge only if every link checks out. Edit one row and it goes red and names the
row. Each decision also mints a standards-shaped attestation bound to the exact graph context the
reviewer saw. That is the audit trail a post-incident review can actually trust."

## 2:38 to 2:50  Close

ON SCREEN: scroll back to the title; the repo and live links.

SAY:
"Keystone. It X-rays the hazards in the Orbit graph that the review surface structurally cannot
see, then governs the change with a gate nobody can quietly bypass. It is a GitLab-native
extension that consumes Orbit, built for the Transcend hackathon. The code and the live demo are
linked below. Thanks for watching."

ON SCREEN TEXT (last frame, hold 3 seconds):
  github.com/vaibhav4046/keystone   .   vaibhav4046.github.io/keystone

---

## If you must cut to fit 3:00

Cut in this order: drop the review-debt beat (1:05 to 1:18), then shorten the AI beat to one
sentence ("a real bounded agent that calls the engine for facts and recommends, but never
produces a number and never records a decision"). Never cut the collision beat or the BLOCK beat;
those are the two that win Technological Implementation and Quality of the Idea.

## Honesty guardrails for the narration (do not drift from these)

- Do not say "live" while recording the SNAPSHOT deploy. Say "this is a committed real index of
  this repository" if the badge reads SNAPSHOT.
- Do not claim the identity is cryptographically verified in the browser demo. It is self-asserted
  there and the banner says so. The OIDC binding is the CI path.
- Do not call it a finished product or claim users or revenue. It is a working prototype with a
  real engine and an honest scope.
