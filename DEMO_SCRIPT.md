# Keystone — 3-minute demo video script

The video is the single highest-leverage thing left (every judge panel said so). This is a
shot-by-shot script wired to the actual live UI at https://vaibhav4046.github.io/keystone/.
Record at 1280x720+, screen capture, talk over it. Target 2:40, hard cap 3:00. Every claim
below is true of the shipped build — do not embellish.

Tools: any screen recorder (OBS, the Windows Game Bar Win+G, or Loom). One take is fine.

---

## 0:00–0:20 — The problem (talk over the landing hero)

On screen: the landing page. Headline "Merge requests that break together".

Say: "Two merge requests pass review. They touch different files, so Git reports no conflict.
They still take down production together — because both change a function the same downstream
code depends on. Git, the merge-request diff, and CODEOWNERS are all blind to it. Keystone is
the one thing that sees it, on the GitLab Orbit call graph."

Point at the "What Git can't see" card: "Here's a real one from Keystone's own code."

## 0:20–0:35 — Real Orbit data, not a mock

Click **Try a live demo**.

Say: "This loads a real GitLab Orbit index — the actual gl_definition and gl_edge tables Orbit
produces. Watch the badge: REAL GitLab Orbit graph. Every number you're about to see is computed
by a deterministic engine from that graph. No LLM is on the number path."

Point at the dashboard provenance badge and the "Definitions indexed: 262" stat.

## 0:35–1:05 — The silent collision + the safe merge order

On screen: Command Center. Point at SILENT COLLISION FOUND.

Say: "compute_blast_radius and verify live in different files — core/impact.py and core/audit.py.
No Git conflict. But five functions depend on both. Merge both MRs and those five break together."

Scroll to **All silent collisions — 16 found**.

Say: "And it's not one. Keystone scans every pair of high-risk changes and finds all sixteen
collisions, each with its shared-dependent count — every pair is grep-verifiable. Then it computes
a safe merge order so you can land them without the break." (Point at the safe merge order line.)

## 1:05–1:35 — The recognizable proof: pallets/click

Go back (click the logo), then click **Demo on pallets/click**.

Say: "This isn't just our own code. Here's a real Orbit index of pallets/click — a library most
Python developers have used. 1,841 definitions. Keystone flags Context colliding with HelpFormatter
across core.py and formatting.py, and it ranks Context as a single point of failure: eighty-one
definitions depend on it. Change Context carelessly and that's your blast radius."

(This is the slide that kills the 'toy example' objection — let it breathe.)

## 1:35–2:05 — Governing AI-agent merge requests

Left rail → **Engineering Harness**.

Say: "AI coding agents now open merge requests faster than any human can hold the context between
them. Keystone runs every bot MR through the same blast-radius pipeline a human reviewer gets —
symbol resolve, blast radius, policy gate, collision scan — and returns ALLOW, HOLD, or BLOCK.
Here a bot MR is BLOCKED. An agent can't approve its own out-of-scope change."

## 2:05–2:35 — The tamper-evident ledger (do this live)

Left rail → **Audit Ledger**.

Say: "Every decision is hash-chained. These hashes are computed live in your browser."

Click **Simulate tamper**.

Say: "I just edited a past decision. Watch — every hash after it recomputes and the chain goes
BROKEN. You cannot quietly rewrite an approval." Click **Restore chain**: "Restore, and it
re-validates. The production ledger uses keyed HMAC-SHA256."

## 2:35–2:55 — The Orbit cross-check + close

Back on the landing, click the green **Cross-checked 120/120 symbols** chip.

Say: "And it's honest by construction. For 120 symbols we ran Orbit's own CLI — glab orbit local
sql — and the count Orbit returned matched Keystone's engine exactly. Here are the real commands."

Close: "Keystone: it reads the GitLab Orbit graph, vetoes a merge two humans already approved, and
binds that decision to a record nobody can edit. The hazard no other tool on the review surface can
see."

---

## Recording checklist
- [ ] Both demos load (Try a live demo -> keystone; Demo on pallets/click -> Context x HelpFormatter).
- [ ] Simulate tamper turns the chain BROKEN; Restore chain returns it to VERIFIED.
- [ ] The 120/120 cross-check modal opens and shows real `orbit sql` commands.
- [ ] No browser console errors during the take (they have held at zero all build).
- [ ] Under 3:00. If long, cut the harness section (2:05) first; keep the click demo and the ledger.

## What NOT to say (honesty guardrails)
- Do not claim cryptographic identity or signed commits — the demo ledger is HMAC-style, disclosed.
- Do not claim org-wide impact numbers the graph can't produce.
- Do not call the in-browser hash SHA-256 — it is a fast FNV demo of the mechanism (disclosed).
- The 120/120 cross-check is a build-time artifact, served static — say "we ran", not "running now".
