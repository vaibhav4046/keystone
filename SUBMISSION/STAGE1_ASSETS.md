# Keystone — Stage 1 Submission Assets (paste-ready)

Everything below is final copy. Paste each block where the form asks for it. The only steps that
need your account are: pasting into the AI Catalog form, recording the video, and clicking Deploy.
Every number here is real and reproducible (see "Demo commands").

- **Live demo:** https://vaibhav4046.github.io/keystone/
- **GitLab repo (PRIMARY — required by the rules):** https://gitlab.com/lalwanivaibhav079/keystone
- **GitHub mirror:** https://github.com/vaibhav4046/keystone
- **Track:** GitLab Transcend Hackathon — Showcase
- **License:** MIT

---

## 1. Project title

```
Keystone — consequence-aware merge governance on the GitLab Orbit graph
```

## 2. Tagline (one line)

```
Git sees files. Orbit sees relationships. Keystone blocks the merges that break together — and records the decision where no one can quietly edit it.
```

## 3. Short description (≤ 280 chars)

```
Two merge requests can pass review, touch different files, have no Git conflict — and still break production together. Keystone reads the GitLab Orbit call graph, blocks those silent collisions before merge, gates AI-authored MRs, and logs every decision in a tamper-evident ledger.
```

## 4. Long description

```
Keystone is a GitLab-native governance layer that turns the Orbit code knowledge graph into a merge gate.

THE PROBLEM. Git's conflict detection is textual: it only flags overlapping line edits. So two merge requests can change entirely different files, pass review independently, and still break production together — because one changes a function the other's change depends on. There is no text conflict, so Git, the MR diff, and CODEOWNERS are all blind to it. As AI coding agents open MRs faster than any human can hold the context between them, the number of these silent collisions only grows.

WHAT IT DOES. Keystone computes each change's blast radius from the real Orbit call graph (gl_definition / gl_edge), then:
  • Shadow Merge Firewall — detects cross-MR collisions Git cannot see, classifies how dangerous each is (same_change / change_in_blast / blast_overlap), and returns a safe merge order from a topological sort (or reports the cycle that makes one impossible).
  • Orbit Memory Gate — refuses an approval that contradicts a prior identical-blast rejection, so project memory can overrule even an AI agent's APPROVE.
  • Agent governance — gates autonomous coding agents against a committed scope manifest and binds each decision to a verifiable identity (GitLab OIDC on the CI path).
  • Tamper-evident ledger — every approve/reject is appended to an HMAC-SHA256 hash-chained log; change one row and the whole chain visibly breaks.

WHAT IS REAL. The engine is fully deterministic — no model on the decision path. Every figure is computed from a real `orbit index` and cross-checked against a live `glab orbit local sql` query that returns the same number. 115 tests pass. The same engine that runs on Keystone's own 262-definition index also finds genuine collisions on pallets/click (1,841 definitions, 6,305 edges) — a third-party library it did not write — so it is not tuned to our own code.

WHAT IS HONEST. The static browser demo chains the ledger with a fast FNV-1a hash to show the mechanism; production uses keyed HMAC-SHA256. In the static demo the reviewer is self-asserted; on the GitLab CI path the runner's OIDC token binds the actor. These are labelled in the UI, not hidden.

The AI assistant explains a change in plain language but is advisory only — it proposes, the deterministic gate decides.
```

## 5. AI Catalog submission description (the catalog field)

```
Keystone is a deterministic, GitLab-native merge-governance engine built on the Orbit code knowledge graph. It surfaces "silent collisions" — pairs of merge requests that pass review and touch different files yet break production together because they share a runtime dependency — and blocks them before merge with a safe merge order. It gates AI-authored merge requests against a committed scope manifest, overrules any approval (human or agent) that contradicts a prior identical-blast rejection, and records every decision in an HMAC-SHA256 hash-chained, tamper-evident ledger bound to a GitLab OIDC identity on the CI path.

The decision path uses no LLM: every blast-radius and collision figure is computed from a real `orbit index` and cross-checked by a live `glab orbit local sql` query. An optional AI assistant explains changes in natural language but is advisory only. Proven on the project's own 262-definition index and on a third-party repo (pallets/click, 1,841 definitions). Open source (MIT). Live demo and one-command CLI included.
```

## 6. Video script (2–3 minutes, ~430 words)

> Tone: calm, confident, fast. Read the bracketed [ACTION] cues to yourself; say only the quoted lines.

```
[0:00] [SCREEN: terminal, repo open]
"Two merge requests can both pass review, touch completely different files, have zero Git
conflict — and still take down production together. Git can't see it. Keystone can."

[0:12] [ACTION: run the headline command]
"One command. Two merge requests. MR-204 speeds up compute_blast_radius. MR-207, in a different
file, edits impact() — a function that depends on it."
$ python skills/keystone/run_review.py shadow-merge
"Git: no conflict. But on the Orbit call graph, MR-207's change lands INSIDE MR-204's blast
radius. Verdict: BLOCK. Exit code 2 — the pipeline fails, on purpose."

[0:35] [ACTION: run the safe pair]
$ python skills/keystone/run_review.py shadow-merge --safe
"Same engine, a non-overlapping pair. ALLOW. Exit 0. It's not blocking everything — it's
blocking the dangerous combination."

[0:50] [ACTION: run memory-gate --prove]
"Now governance for AI agents. A staff engineer rejects a risky change. Then a coding agent
proposes APPROVE on the same thing."
$ python skills/keystone/run_review.py memory-gate compute_blast_radius --prove
"Keystone recalls the rejection it recorded seconds ago — by content, so it survives a rename
or a re-index — and overrules the agent. BLOCK. The model proposes; Keystone decides."

[1:15] [SCREEN: live site, click 'Try the live demo']
"Same numbers, in the browser. This loads Keystone's REAL Orbit self-index — 262 definitions —
with a provenance badge: gl_definition, gl_edge. Nothing here is mocked."

[1:35] [ACTION: open Reviewer Cockpit]
"The blast-radius graph: five functions break together, twelve in the combined radius. The
panels all agree because they read the same graph."

[1:50] [ACTION: open Audit Ledger, click Simulate tamper]
"Every decision is hash-chained. Edit one past row — watch every downstream hash break.
Restore — it re-validates. No one edits an approval quietly."

[2:10] [ACTION: click 'Demo on pallets/click']
"And it's not tuned to our own repo. Here's the same engine on pallets/click — eighteen
hundred definitions of a library we didn't write — finding real collisions."

[2:25] [SCREEN: README 'How to verify this is real']
"Everything you saw is reproducible in two minutes, and 115 tests prove it. Git sees files.
Orbit sees relationships. Keystone sees consequences — and blocks them before they ship."

[2:40] END
```

## 7. Recording sequence (exact clicks)

1. Terminal, repo root. Font large. Run, in order:
   - `python skills/keystone/run_review.py shadow-merge` → point at **VERDICT: BLOCK** and the relationship-path line.
   - `python skills/keystone/run_review.py shadow-merge --safe` → point at **VERDICT: ALLOW**.
   - `python skills/keystone/run_review.py memory-gate compute_blast_radius --prove` → point at **[1/2] recorded** then **OVERRIDES the agent**.
2. Browser, https://vaibhav4046.github.io/keystone/ → click **Try the live demo** → wait for the green **REAL GitLab Orbit graph** badge.
3. Left rail → **Reviewer Cockpit** → show the blast graph (now renders) + the rings panel.
4. Left rail → **Audit Ledger** → **Simulate tamper** (chain turns BROKEN, ≠ appears) → **Restore chain**.
5. Back to Home → **Demo on pallets/click** → show the indexed third-party graph.
6. Show the README **"How to verify this is real"** table for 3 seconds.

Keep total under 3:00. If short on time, cut step 5; never cut steps 1, 2, 4.

## 8. Demo commands (copy-paste, all reproducible)

```bash
pip install -r requirements.txt
python -m pytest -q                                                     # 115 passed, 2 skipped

# THE hook — directional collision, two safe changes unsafe together → BLOCK, exit 2
python skills/keystone/run_review.py shadow-merge
# the safe counter-example → ALLOW, exit 0
python skills/keystone/run_review.py shadow-merge --safe
# AI governance — record a real reject, then overrule an agent's APPROVE from it → exit 2
python skills/keystone/run_review.py memory-gate compute_blast_radius --prove
# the full sample review for MR-204
python skills/keystone/run_review.py harness sample

# Generality — same engine on a third-party repo it did not write (pallets/click)
python skills/keystone/run_review.py shadow-merge --graph data/click_graph.duckdb --a Context --b echo
python skills/keystone/run_review.py shadow-merge --graph data/click_graph.duckdb --a echo --b make_context
```

## 9. Deployment checklist

Static demo (already live, GitHub Pages):
- [ ] GitHub repo Settings → Pages → Source = `main`, folder = `/web` IF available; otherwise the Pages
      action serves `web/`. Confirm https://vaibhav4046.github.io/keystone/ loads and **Try the live demo**
      shows the green Orbit badge. (Note: Pages cannot set HTTP headers; the CSP ships as a `<meta>` tag.)
- [ ] Confirm the GitLab mirror is public and current: https://gitlab.com/lalwanivaibhav079/keystone
      (`git push gitlab main` after merging, see §11).

Live backend (optional, lets a remote judge hit the real agent + live `orbit sql`):
- [ ] render.com → New → Blueprint → connect the GitHub repo → Apply (uses `render.yaml`, free tier, no card).
- [ ] Health check: `https://<your-render-url>/api/health` returns ok.
- [ ] (Optional) Add `OPENROUTER_API_KEY` (or CEREBRAS/GROQ/GEMINI) under Environment to light up the real
      LLM brief + agent. Never commit the key. Without it, the live demo runs the deterministic plan.
- [ ] Confirm security headers: `curl -sI https://<your-render-url>/ | grep -i content-security-policy`.

## 10. Judge notes (what to look at, and why it's credible)

- **The wedge in one sentence:** Git's conflict check is textual; the call graph is relational. Keystone
  gates on the relationship Git structurally cannot see.
- **No LLM on the decision path.** The verdict is a deterministic graph computation. The AI assistant is
  advisory and clearly labelled "tool-using agent — it proposes, it never decides".
- **Numbers are observed, not asserted.** Each ring-1 count is cross-checked against a live
  `glab orbit local sql` query; `tests/test_engine.py::test_independent_recompute_matches` recomputes the
  set with raw SQL. 120/120 self-graph symbols match.
- **It generalises.** `tests/test_external_repo.py` finds real collisions on pallets/click.
- **It's honest about its demo seams.** FNV-1a (browser) vs HMAC-SHA256 (backend); self-asserted (static)
  vs OIDC-bound (CI). Both are labelled in the UI and in the README verify table.
- **Strongest 90 seconds:** the BLOCK→ALLOW pair (deterministic gate), the memory-gate `--prove` override
  (AI governance), and the ledger tamper (auditability).

## 11. After approval: ship the branch (your account, one command set)

The fixes live on the `winner-ready` branch. To publish:

```bash
git checkout main
git merge --no-ff winner-ready -m "Merge winner-ready: judge-readiness fixes"
git push origin main          # GitHub (also drives GitHub Pages)
git push gitlab main          # GitLab mirror (primary submission repo)
```

(If you prefer, open a PR from `winner-ready` → `main` on GitHub and merge in the UI.)
