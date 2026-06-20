# Keystone — Master Design Brief

> Paste this whole file into the design tool. It is the complete context: the product, the
> hackathon it's for, who it's for, every screen, the brand, the exact copy, and the honesty
> constraints. Design the most striking, premium, *credible* version of this product.

---

## 0. One line

**Keystone finds the merge requests that pass every review and still break production together.**

Tagline: **"See Everything. Impact Nothing."**

---

## 1. What it is (elevator)

Two engineers open two merge requests. Different files. No Git conflict. Both get approved.
They merge. Production breaks — because both changed functions that the *same* downstream code
depends on. Git can't see it. Code review can't see it. CODEOWNERS can't see it.

Keystone can. It reads the repository's **call graph** (via GitLab Orbit) and computes each
change's **blast radius** — everything that transitively depends on it. When two pending changes'
blast radii **overlap**, that's a **silent collision**: the 2am production break that no
file-diff tool warns you about. Keystone surfaces it *before* the merge, shows exactly who's
affected, tells you how to resolve it, and records the decision in a tamper-evident audit ledger.

It also gates **AI coding agents**: when a bot opens an MR, Keystone decides if it's safe to merge.

---

## 2. The hackathon context (design for the judges)

- **Event:** GitLab Transcend Hackathon — **Showcase track** (Devpost).
- **Judging:** 4 **equally-weighted** categories, each with a 1st + 2nd cash prize:
  1. **Technological Implementation**
  2. **Design & Usability**  ← *this brief is the lever for this one*
  3. **Potential Impact**
  4. **Quality of the Idea**
- **Win model:** place **top-2 in ONE category**, not best overall. So the design must be
  *unmistakably* premium and intentional — "best design they saw all event," not "fine."
- **What judges do:** open a live URL, click around for 60–120 seconds, maybe skim a 3-min video.
  The **first 5 seconds** decide everything. Landing → instant "whoa" → instant "I get it."
- **Required honesty:** this is a real working tool, not a mockup. Numbers are computed from a
  real graph. **Never invent metrics or fake testimonials.** Design must *look* premium without
  *claiming* anything untrue. (See section 9.)

---

## 3. The problem, told well (use this as narrative spine)

**"The 2am break."**
- MR-A changes `echo()` in `utils.py`. MR-B changes `option()` in `decorators.py`.
- Different files -> **no Git conflict**. Both pass review independently.
- But 34 functions call **both** `echo` and `option`. Change both -> those 34 break together.
- Each reviewer saw a safe, small diff. Nobody saw the overlap. That's the silent collision.

Keystone's job: make that invisible overlap **visible, quantified, and fixable** before merge.

---

## 4. The product flow (the screens to design)

A judge moves through these in order. Each is a "screen" to design.

### 4.1 Landing (the 5-second hook) — MOST IMPORTANT
- Full-bleed, cinematic, dark. The angular **K** logo, the word **Keystone**, the problem in
  two sentences, two CTAs: **"Sign in with GitHub"** (primary) + **"Try a live demo"** (secondary).
- Subtext: "No account needed for the demo — Keystone analyzes real public repos in your browser."
- Footer line: **See Everything. Impact Nothing.**
- This screen must feel like a funded product's homepage, not a hackathon project.

### 4.2 Onboarding moment ("The 2am break")
- A single focused card that tells the problem story in 3 short beats, ending with a button:
  **"Show me a collision Git can't see."** One click -> a real finding appears.

### 4.3 Command center / Overview (the dashboard)
- Top nav: Dashboard, Inventory, Analysis, Reports, Overview + search + notifications + avatar.
- Hero block: big "Keystone" + "Real-time impact intelligence" + Start Analysis / View Dashboard.
- **Blast Radius radial** — a central glowing K with orbiting dependency nodes on concentric rings.
- Stat cards (wired to the *real* analysis): **Definitions indexed**, **Max blast radius**,
  **Silent-collision dependents**.
- **Impact Over Time** area chart. **Dependency Chain** vertical connected list (real symbols).
- **Impacted Entities** table (symbol, type, impact level, status).
- **Recent Events** feed.

### 4.4 The finding card (the payoff)
- "SILENT COLLISION FOUND — in `owner/repo`, changing `echo` (utils.py) and `option`
  (decorators.py) — different files, no Git conflict — both ripple into **34** shared runtime
  dependents. Two merge requests that pass review and break together."
- Then **"How to resolve"** — 3 concrete steps (integration test covering both, single stacked
  review, or flag-gate the second). Detect -> resolve.
- A button: "Explore the blast radius ->".

### 4.5 Reviewer Cockpit (the depth)
- A real **3D / radial blast-radius graph** of a chosen symbol: epicenter + rings of dependents,
  edges following the real call graph, animated reveal, a live counter of "N affected."
- Side panels: the symbol list, the impact rings (direct / 1-hop), an ALLOW / HOLD / BLOCK verdict.

### 4.6 Engineering Harness (the AI-agent angle)
- "Coding agents can write patches. Keystone decides if they're safe to merge."
- A bot MR (e.g. `copilot-workspace`) runs a 5-step pipeline: Symbol Resolve, Blast Radius,
  Policy Gate, Collision Scan, Verdict. Per-symbol result + an overall **BLOCK / ALLOW** verdict.

### 4.7 Audit Ledger (the trust)
- A hash-chained, tamper-evident decision log: #, time, change (MR id), blast, reviewer, decision
  (approve/reject), hash (prev -> this). A "CHAIN VERIFIED" badge. A "Simulate tamper" control that
  flips it red. Honest label: this public sample uses a shared key, so it's illustrative.

### 4.8 Live Demo (the auto-play)
- A 5-step "future merge simulator" with an **Auto-play** button: it advances itself, each step's
  text acting as a subtitle, like a guided video. Pause + restart.

### 4.9 Sign-in consent (CLI-flavored)
- A terminal-styled modal: `$ keystone auth --connect github`, read-only permissions list,
  Allow / Demo. Reads like a developer tool, not a marketing popup.

---

## 5. Who it's for (personas — design for these eyes)

- **Staff engineer** — owns a service many teams depend on; lives in fear of the silent break.
  Wants the blast radius at a glance, trusts numbers only if they're traceable.
- **CODEOWNERS / reviewer** — approves MRs all day; can't hold the whole graph in their head.
  Wants "is this change bigger than it looks?" answered in one screen.
- **Compliance / platform lead** — needs every merge decision logged, attributable, tamper-evident.
  Wants the ledger and the governance gate.
- **The hackathon judge** — no account, 90 seconds, has seen 200 dashboards. Must feel something
  in 5 seconds and understand it in 30.

---

## 6. Brand & visual direction

**Pick a bold, opinionated direction — not "clean minimal."** The chosen direction is:

### Fire / ember + dark command-center
- Cinematic near-black base, warmed toward ember: `#0c0805` / `#0a0b0e`. **Not** flat black.
- A **fire glow rising from the bottom** of the page; **drifting ember particles** rising slowly.
- Vibrant, *popping* orange as the one rationed accent. Flame gradients on primary actions
  (yellow -> orange -> red).
- A faint terminal/CLI undertone (mono type for machine truth, a prompt glyph on the input).
- Optional hero art: a stylized ember/pixel character (lava-edged) standing beside the dashboard,
  subtle float + ember-glow animation. Cinematic, not cartoonish.

### Logo
- **Angular, faceted orange "K"** — a sharp geometric mark (vertical stem + two detached angular
  arms), gradient `#FFB14D -> #FF7A1A -> #F0480A`, soft glow. Used as favicon, nav, avatar, landing.

### Color tokens
- Accent orange: `#FF7A1A` (deep `#F0480A`, hot `#FFC24D`).
- Surfaces: `#131519` / `#16181E`, borders `rgba(255,255,255,0.07)`.
- Text: `#F2F3F5` / muted `#8B9099` / dim `#5F636D`.
- Semantic: high/impacted = orange-red `#FF6A3D`; medium/degraded = amber `#F5A623`;
  verified/good = green `#34D399`.

### Typography
- **Display:** Space Grotesk (or a confident geometric grotesque) — big, tight, `-0.03em`.
- **Body:** Inter / system sans.
- **Machine truth (hashes, symbols, counts, CLI):** JetBrains Mono. Use tabular figures for numbers.

### Motion (compositor-friendly only)
- transform / opacity / filter. Ember rise, fire flicker, radial slow-rotate, counter count-up,
  blast-radius reveal. Everything gated behind `prefers-reduced-motion`. No layout-thrash animation.

### Anti-template rules
- No default card grid with uniform everything. Use hierarchy through scale contrast, intentional
  rhythm, layering/depth, editorial composition. Hover/focus/active states must feel *designed*.
- It must read as a real, shipped, funded product in a screenshot.

---

## 7. Exact copy (use verbatim where you can)

- Hero headline: **Stop safe-looking merge requests from breaking production.**
- Hero thesis: *Two merge requests can pass review, touch different files, have no conflict, and
  still break production together. Keystone catches that on the GitLab Orbit call graph before you merge.*
- Landing pitch: *Two merge requests can pass review, touch different files, have no conflict — and
  still break production together. Sign in to catch those silent collisions on your repo's call
  graph before you merge.*
- Finding: *SILENT COLLISION FOUND — changing X and Y, different files, no Git conflict, both
  ripple into N shared runtime dependents. Two merge requests that pass review and break together.*
- Tagline: **See Everything. Impact Nothing.**
- Onboarding CTA: **Show me a collision Git can't see.**
- Section names: Blast Radius, Dependency Chain, Impacted Entities, Recent Events, Reviewer
  Cockpit, Engineering Harness, Audit Ledger, Live Demo.

---

## 8. Layout / responsiveness

- Desktop-first cinematic, but every screen must collapse cleanly to **375px** (single column,
  no horizontal scroll). On mobile: hide decorative provenance chips, collapse the sign-in to an
  icon, keep the hero headline wrapping nicely.
- Sidebar is a narrow icon rail (~64px). Brand mark sits at its top.
- Keep content above the fire/ember background layers (z-index discipline).

---

## 9. Honesty constraints (non-negotiable — design around these)

- It analyzes **code** (definitions, call-graph blast radius). Any "services / users affected"
  framing is illustrative; the *real* metrics are definitions indexed, blast radius, shared
  dependents. Prefer the real ones; label anything illustrative as a **demo snapshot**.
- Blast numbers are **direct dependents** (grep-verifiable), not inflated transitive guesses.
- The audit chain on the public demo uses a shared key -> label it **SAMPLE / PUBLIC KEY**
  (illustrative, not cryptographically tamper-proof in the demo).
- Real GitHub OAuth (private repos) requires a deployed backend; the static demo connects **public**
  repos in-browser. Don't imply private access that isn't there.
- No fabricated testimonials, no fake "10,000 users," no invented uptime. Premium look, honest claims.

---

## 10. What to deliver

Design, in this priority order:
1. **Landing** (light + the hero hook) — the 5-second win.
2. **Command center / Overview** (the dashboard with Blast Radius radial + real stat cards).
3. **Reviewer Cockpit** (the blast-radius graph deep-dive).
4. **The finding card + "How to resolve"** component.
5. **Audit Ledger** + **Engineering Harness** + **Live Demo** + **CLI sign-in consent**.
6. A small **design system**: color tokens, type scale, the K logo lockups, button states
   (primary flame / secondary / ghost), card/surface styles, the ember/fire background treatment,
   chip + badge styles, table style, the radial-graph style.

Deliver as: high-fidelity screens (desktop + 375px mobile for each), plus the token/style sheet,
so it can be implemented 1:1 in HTML/CSS.

---

## 11. Reference points (vibe, not copy)

- Linear / Vercel dashboards (restraint + depth), Hermes by Nous Research (one bold saturated
  color field + confident display type + a CLI command box), Claude's landing (sign-in-gated, calm
  authority), classic "command center" SOC dashboards (dense but legible). Take the *confidence* of
  these, apply the **fire/ember + angular-K** identity, and make it unmistakably Keystone.
