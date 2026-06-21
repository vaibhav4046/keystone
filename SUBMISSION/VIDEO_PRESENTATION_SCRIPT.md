# Keystone demo video: full script + navigation

Two parts. The presentation deck (web/present.html, screen-recorded) opens the video,
then you cut to the live product and do a real task. Devpost caps the video at 3 minutes,
so the SUBMISSION CUT below is the one you upload. The EXTENDED walkthrough is for practice
or a longer talk. Record at 1280x720 or 1920x1080. Speak in a calm, confident voice.

Open two browser tabs before you start:
- Tab A (presentation): https://vaibhav4046.github.io/keystone/present.html  (press F for fullscreen)
- Tab B (live product): https://vaibhav4046.github.io/keystone/
- A terminal in the repo folder.

Keys in the deck: Right arrow / Space = next, Left = back, F = fullscreen.

---

## SUBMISSION CUT (target 2:40, hard max 3:00)

### Part 1: Presentation (about 60 seconds, Tab A, fullscreen)

- Slide 1 (title). "Keystone is the first merge gate for AI coding agents, built on the
  GitLab Orbit code graph."
- Slide 2 (the problem). Press Right. "Here is the problem. Two merge requests each pass
  review. They touch different files, there is no Git conflict, and they still break
  production together, because one changes a function the other depends on."
- Slide 3 (why review misses it). Press Right. "Git compares files. CODEOWNERS routes by
  ownership. Merge trains re-run CI. None of them see it. The break lives in the call
  graph."
- Slide 4 (the insight, animated graph). Press Right. "Orbit gives us that graph. Keystone
  reads the transitive intersection of two merge requests, the shared dependents that
  break together."
- Slide 5 (the gate). Press Right. "It turns that into a deterministic verdict. Allow,
  hold, or block, with required approvers, recorded in a tamper-evident ledger. No language
  model decides anything."
- Slide 6 (AI-agent gate). Press Right. "And it is built for autonomous agents. An agent
  cannot approve its own change, and a recorded rejection blocks any later re-approval of
  the same blast signature."
- Slide 8 (any repo). Press Right twice (through slide 7). "It runs on any repo with zero
  pre-indexing, so it is a CI control any team can drop in, not just Orbit-Local orgs."
- Slide 9 (close). Press Right. "Git sees files. Orbit sees relationships. Keystone sees
  consequences. Let me show you the live product."

### Part 2: Live product, a real task (about 100 seconds, Tab B)

1. Land on the hero. "This is live, no install. The demo is playing in the corner."
   (the 90-second demo autoplays on its own.)
2. Click "Sign in with GitHub" (top right). Approve. "Real OAuth. Now it lists my own
   repositories."
3. Left rail, open Reviewer Cockpit. Pick the symbol compute_blast_radius. Click
   "Gate as an AI-agent MR". "I am asking the deployed engine to gate a change to this
   function as if an AI agent opened the merge request. The verdict comes back from the
   server: the tier, the required approvers. No model in that path."
4. Click "Run REAL duckdb-wasm SQL in your browser". "And this is the same Orbit query
   running in my browser, on the real graph, not a recording. It returns twelve. The
   backend returned twelve. The tests return twelve. They converge."
5. Cut to the terminal. Run:
   `python skills/keystone/run_review.py scan-repo benjaminp/six`
   "This is the part that matters for adoption. I am pointing it at a public repo it has
   never seen. It fetches the code, builds the Orbit graph on the fly, and gates it. Zero
   pre-indexing. Any team can run this in CI today."
   Then run a real diff gate:
   `git diff | python skills/keystone/run_review.py changed-symbols --fail-on-block`
   "And here it reads a real diff, finds the changed symbols itself, gates them, and exits
   non-zero on a block. That is the autonomous CI gate."
6. Back to Tab B, open Audit Ledger. Click "Simulate tamper". "Every decision is hash
   chained. If anyone edits a past decision, the chain breaks, visibly." Click "Restore".
7. Close on the hero. "Keystone. The deterministic merge gate that holds AI coding agents
   accountable, on the GitLab Orbit graph. Thank you."

---

## EXTENDED WALKTHROUGH (5 to 6 minutes, for practice or a talk, not the upload)

Same Part 1 presentation, then a fuller Part 2:
- Dashboard overview: read the silent-collision finding and the "All silent collisions"
  table. Explain blast radius and the shared-dependents count.
- Engineering Harness: show a bot merge request run to a BLOCK verdict, then the
  "Agent fix plan" card and the "Copy fix plan" button. Note the advisory chip: the plan
  is advisory, the gate is deterministic.
- "Why Git and GitLab can't catch this" card: walk the comparison row by row.
- Live backend proof panel: source mode, definitions, audit chain, no LLM on verdict.
  Click "/api/status" to show the raw JSON.
- Analyze any public GitHub repo: paste your own repo, watch it fetch and build the graph
  live in the browser.
- pallets/click external proof: 1,841 definitions, a library we did not write, real
  collisions found.
- Terminal extras: `run_review.py demo` (the whole story in one command),
  `run_review.py shadow-merge` (BLOCK, exit 2), `run_review.py memory-gate
  compute_blast_radius --prove` (a recorded rejection overrules an agent approval).

---

## Recording tips

- Pre-warm the backend: open https://keystone-zt6c.onrender.com/api/health once before
  recording so the first live click is instant.
- If the backend is cold mid-demo, the page says "warming" and the in-browser duckdb-wasm
  button still proves the live SQL with no backend. Use that.
- Keep cuts tight. The first ten seconds decide attention: open on the problem sentence,
  not on a logo.
- No copyrighted music. Voice only, or a royalty-free bed.
