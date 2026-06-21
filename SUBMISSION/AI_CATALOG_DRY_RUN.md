# Keystone - AI Catalog Dry-Run QA

Paste-ready fields live in `SUBMISSION/STAGE1_ASSETS.md` (AI Catalog section). Pre-publish checklist,
verified this pass.

| Check | Result |
|---|---|
| Title | YES - "Keystone - Orbit merge-collision governance" |
| Short description | YES - one paragraph, no fluff |
| Long description | YES - deterministic, no-LLM-verdict, Orbit-native, proven on pallets/click |
| Install instructions | YES - `git clone … && pip install -r requirements.txt` |
| Usage instructions | YES - `run_review.py demo` / `shadow-merge` / `--safe` / `memory-gate --prove` |
| Verification commands | YES - `pytest -q` (115) + `shadow-merge --graph data/click_graph.duckdb` |
| Security model | YES, honest - HMAC-SHA256 prod / FNV-1a static demo; OIDC on CI / self-asserted static; CSP + SRI |
| Limitations | YES, honest - static call-graph approx; published-key static ledger; content-key rename limit; no live MR webhook |
| Links (live, backend, GitHub, GitLab) | YES - all 200; video URL pending |
| Why it matters for GitLab Duo / Orbit | YES - agent-velocity → more relationship collisions → Orbit exposes the graph → Keystone gates it |
| No placeholders except video | YES |

## Publish procedure (when the form is open)
1. Sign in to GitLab AI Catalog.
2. Paste fields from STAGE1_ASSETS.md "AI Catalog" section.
3. Set visibility Public; confirm no placeholder remains (video optional here).
4. Publish → capture the catalog URL → I add it to FINAL_10_PACKET.md and push.

## Status
- Completed: all fields verified, links resolve.
- Waiting for user login or approval: GitLab AI Catalog sign-in to publish.

---

## 2026-06-21 - agentic-governance framing strengthened

The Agent fix plan card makes the "Keystone governs AI-agent merge requests"
story concrete: a blocked bot MR now gets a deterministic remediation plan
(stack, test, safe merge order, re-run gates, record to ledger) with an explicit
"advisory - gate is deterministic" disclosure. Good material for the AI Catalog
capability description.
