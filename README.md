# Keystone

[![ci](https://github.com/vaibhav4046/keystone/actions/workflows/ci.yml/badge.svg)](https://github.com/vaibhav4046/keystone/actions/workflows/ci.yml)

Keystone X-rays the GitLab Orbit code knowledge graph for risk that the review surface structurally cannot see, then governs the change with a deterministic, tamper-evident gate. The lead is the hazard, not the gate.

Two hazards the graph knows and Git does not. The first is a cross-MR blast collision: two open merge requests can touch entirely different files, pass review independently, and still break together, because one changes a function the other's change depends on. There is no textual conflict, so Git, the MR diff, and CODEOWNERS are all blind to it; the call graph is not. Keystone finds the collision, classifies how dangerous it is, and computes a safe merge order (or reports the cycle that makes one impossible). The second is review debt: a symbol with a large blast radius that no test file directly exercises is a change that is at once high-impact and unverified, and the graph can rank exactly those. Both are deterministic graph computations, not a model's guess.

Then it governs. Orbit gives the blast radius of a single change; Keystone maps that impact to a policy tier that sets required approvers and an ALLOW / HOLD / BLOCK action, refuses an approval that contradicts a prior identical-blast rejection, gates autonomous coding agents against a committed scope manifest, takes the union blast radius across a multi-symbol merge request, and mints a tamper-evident, standards-shaped attestation for every decision recorded in an HMAC hash-chained ledger. The differentiator is not the blast-radius view, which GitLab markets; it is reading the graph for hazards nobody else surfaces and binding the decision to a record nobody can quietly edit.

A GitLab-native extension, not a standalone product: it consumes Orbit, drives Orbit's own CLI, ships as a project SKILL.md plus a CI governance gate, and is built for the GitLab Transcend Hackathon, Showcase track. The onboarding path is a merge-request hook (or the committed `.gitlab-ci.yml` gate) that calls the Keystone API on the touched symbols and fails the pipeline on a BLOCK.

Live demo: https://vaibhav4046.github.io/keystone/ — status SNAPSHOT: a committed real `orbit index` of this repo (262 definitions) with every figure cross-verified by `orbit sql`, served static. Stand up the live backend (one-click `render.yaml`) to interact with the agent and the live hazard detection.

## Who it is for, and what breaks today

A staff engineer about to approve a risky refactor needs to see what the change actually touches before they say yes, not after. A platform or CODEOWNERS team enforcing review needs the precedent on a symbol they do not own by heart. A compliance or audit lead, after an incident, has to answer who approved this change, what it touched, and why, from a record nobody could have quietly edited.

Today those questions go unanswered. A merge silently breaks a dozen transitive callers. An approval is recorded with no rationale. A post-incident audit cannot be reconstructed because the log was editable. And increasingly a change proposed by an autonomous coding agent reaches main with no human-auditable gate at all. Keystone is the gate.

Concretely: a ten-person platform team inside a 500-engineer company merges a change to a shared utility that quietly breaks twelve transitive callers; it ships, pages on-call at 2am, and becomes a P2 that burns roughly forty engineer-hours across triage, rollback, and the post-incident review reconstructing who approved what and why. At a loaded 100 dollars an hour that single incident is about four thousand dollars, before the trust cost. Keystone puts the twelve-caller blast radius and the prior rejection in front of the reviewer at the moment of approval, and leaves a record the audit can trust afterward. It is for teams where a change can break code nobody in the review owns; it is not for a solo project where the author already holds the whole graph in their head.

## What it does

Point Keystone at a set of open merge requests and it runs the hazard X-ray over the Orbit graph: which MRs collide on the call graph despite no Git conflict (`POST /api/collisions`), in what safe merge order, and which high-blast symbols carry review debt because no test directly exercises them (`GET /api/graph-audit`). Both are deterministic graph reads.

Then pick a symbol that is about to change. Keystone reads the GitLab Orbit Local code graph and computes the deterministic blast radius: the direct callers, the transitive dependents to a bounded depth, the owning files and directories, ranked as severity rings out from the epicenter. Every number is computed from the graph by a pure-Python engine and is reproducible; the model never invents a figure. A Precedent Panel surfaces prior governance on the same symbol or the same blast signature, including a contradiction when a pending approval conflicts with a past rejection. A reviewer approves or rejects with a written reason, and the decision is appended to an HMAC-keyed, sha256 hash-chained audit ledger whose integrity is recomputed live, showing a green verified badge only when every link checks out.

## Why this is not branch protection, signed commits, or a CI check

Branch protection enforces who clicked approve. Signed commits and GPG git-notes, Sigstore, and in-toto attest who authored or signed code. None of them bind the computed impact of a change and the human rationale and the decision together into one tamper-evident record at the moment of decision, and none surface a contradicting prior rejection while you are about to approve. That binding, plus precedent at the moment of choice, is Keystone. It is complementary to Sigstore and in-toto, not a replacement: they attest the artifact, Keystone attests the decision.

## Governance as code, attestations, and agent gating

The blast radius is not just shown, it is the enforcement decision. A versioned policy committed at `.keystone/policy.json` maps the engine-computed blast radius (distinct affected files) to a severity tier (ISOLATED, LOCAL, CROSS-TEAM, ORG-WIDE), and each tier deterministically sets a required approver count, a review window, and an ALLOW / HOLD / BLOCK action. The three actions are precise and distinct: BLOCK refuses the approval outright (HTTP 409) unless an accountable, recorded override is supplied; HOLD is a quorum gate, meaning the change is recorded as PENDING_APPROVAL and is not closed until the tier's required number of distinct approvers have signed off (a rejection resets the count); ALLOW closes at one approver. A prior identical-blast-radius rejection forces BLOCK. The review window is displayed by default and becomes a hard time gate when the policy sets `window_enforced`. An unregistered autonomous agent cannot self-approve at all (HTTP 403), and the author of a change cannot approve their own change (four-eyes: HTTP 403 unless an accountable override). Quorum is tracked per change id, so two unrelated merge requests on the same symbol never share an approver pool, and a rejection resets the count. One deliberate strength: a recorded rejection of a blast signature becomes binding precedent, so a later approval of that same signature is BLOCKed until an override, even on a HOLD-tier symbol — you cannot quietly re-approve what was rejected.

To see all of this on the live site: select `audit_log` for the ORG-WIDE / HOLD tier with its three-approver quorum, and `tokenize` for the contradiction-driven BLOCK with the override path. The raw counts are always shown next to the tier label, and the policy's canonical sha256 is pinned into every decision, so an auditor can reconstruct the exact policy in force at any historical approval. This is something CODEOWNERS, a branch-protection rule, or an OPA policy structurally cannot do, because none of them have a code knowledge graph to compute the tier from. Same graph snapshot plus same policy always yields the same tier; no model is on the decision path.

Every decision mints an attestation: an in-toto Statement carrying a SLSA Verification-Summary-style predicate, whose subject digest is the `orbit_snapshot_sha256` of the exact graph context the reviewer saw (epicenter, rings, affected set, owners, signature). That binding closes a gap SLSA and in-toto leave open: they attest the build, Keystone attests the reviewed impact. It is downloadable from the UI and at `GET /api/attestation/{symbol}`, with an offline verifier. The attestation is honest about what it is: Keystone-issued, not a SLSA conformance body; tamper-evident via the HMAC chain, not a cryptographic signature; Sigstore/Rekor keyless signing is named as a future step and explicitly marked false, never claimed.

A note on what "uses Orbit" means, stated plainly: the engine reads the Orbit Local graph database directly (the DuckDB file Orbit itself produces and Orbit's own CLI introspects), and that direct read IS the integration — it is the same graph, not a copy or a workaround. The `glab orbit local` CLI is additionally driven at session start and as a live cross-check so the integration is demonstrable on the surface, and the four further gates on the roadmap consume Orbit Remote. The blast radius, tier, and every governance decision are computed from Orbit's graph; remove the graph and the product has nothing to enforce on.

Agent gating answers the 2026 "who wrote this" problem. A repo-committed registry at `.keystone/agents.json` gives each autonomous coding agent a scope manifest (allowed and forbidden path globs plus a maximum blast radius). A registered agent that opens a change outside its scope is hard-refused at `POST /api/approve` with a SCOPE-VIOLATION; a human reviewer can still decide. Matching is literal fnmatch and set membership, with no ML and no fuzzy matching, and a registry miss is reported as detected-not-proven (AGENT-UNREGISTERED), never as a verified identity.

## Roadmap, and what is deliberately not faked

Three further graph-driven gates are designed but not shipped, because they require Orbit Remote data the free local graph does not contain, and faking them on the sample fixture would be dishonest: a dependency-depth quarantine that blocks an agent-authored lockfile change reaching a known-vulnerable package node; an ownership-entropy gate that joins file diffs against CODEOWNERS and 90-day commit recency to catch stale owners; and a pipeline-health risk multiplier from the CI history recipe. Each is one Orbit Remote query away and is documented rather than mocked.

## The AI assist layer (real, but off the trust path)

Keystone has a working AI layer that explains a governance decision in plain language. `core/llm.py` runs a free provider ladder (Cerebras, Groq, OpenRouter with several free tool-calling models, Gemini), each behind a hard timeout, and turns the engine's already-computed facts into a short reviewer brief at `GET /api/brief/{symbol}` ("this change reaches N dependents across F files, CROSS-TEAM tier, get a second approver").

Beyond the one-shot brief there is a real bounded tool-using agent at `POST /api/assistant` (`core/agent.py`). The model is given three tools, each a thin wrapper over the deterministic engine: `blast_radius`, `precedent`, and `propose_reviewers`. It runs a short ReAct loop (model picks a tool, the engine answers with real facts, repeat) for up to four steps, then recommends a next step. The AI ASSISTANT panel shows the exact tool trace so a reviewer can audit which facts the recommendation rests on. Every tool result is engine-computed, so the model cannot invent a count, a tier, or a signature, and it never records a decision: the agent proposes, the deterministic gate decides. The static deploy bakes a real recorded run (provider-named) for the headline symbols and a deterministic plan for the rest; the live backend runs a fresh loop for any symbol and any question.

When no key has quota both paths fall back to a deterministic template, so the product works with zero keys, and the UI labels the output honestly as "AI · provider" / "agent · provider" or "deterministic". This is the agentic capability, an LLM that drives a trustworthy engine, without letting a model invent the audit trail.

## Integrity model, stated honestly

What the ledger guarantees and what it does not, so the claim is precise rather than marketing:

- Each row's hash is an HMAC over the previous hash plus the canonical payload, keyed by a secret taken from `KEYSTONE_LEDGER_KEY` or generated once and stored outside the repo at `~/.keystone/ledger.key`. Because the key is secret, a party who can read or append to the ledger file still cannot forge a valid tail; recomputing the chain detects both an in-place edit and a forged append. A plain published sha256 chain would not stop a forged append, which is why the HMAC matters. A test (`test_forged_append_with_public_sha256_is_rejected`) proves it.
- Appends are serialised by a process lock, so two concurrent approvals cannot share a previous hash and break the chain. A multi-worker or multi-host deployment needs an external mutex or a database-backed ledger; the single-process server is correct as shipped.
- Reviewer identity is self-asserted in the browser demo unless you set `KEYSTONE_APPROVE_TOKEN`, in which case `POST /api/approve` requires a matching `X-Keystone-Token` header (which proves possession, not identity). On the GitLab CI gate path the actor is bound: the `id_tokens` block in `.gitlab-ci.yml` mints an OIDC token, the runner injects it, and `core/identity.py` binds the recorded actor to its `sub` claim, so the ledger row carries `self_asserted=false` and the bound subject (see `core/gate.py`). The boundary is kept honest: those claims are trusted because the GitLab runner injected the token, and `signature_verified` is recorded as `false` because offline RS256 verification against GitLab's JWKS needs the `cryptography` dependency, which `verify_signature()` is the hook for. So four-eyes and agent gating are advisory in the browser demo and GitLab-attested in the pipeline. A policy-BLOCK override is separately credentialed: when `KEYSTONE_OVERRIDE_TOKEN` is set, an override additionally requires a matching `X-Keystone-Override-Token`, so overriding is not the same privilege as approving. The README does not claim cryptographic identity it does not have.
- The blast-radius signature is computed over the epicenter plus the sorted affected id set, so two unrelated symbols with no dependents do not collide and produce a phantom contradiction. A prior rejection on the same symbol with a different blast radius is shown as a weaker advisory, not a full contradiction.

## Current limitations

The ledger is a per-instance append-only file: one shared store per deployment, not a multi-tenant service. The MR-level union blast radius across several touched symbols, with the strictest tier applied, is available at `POST /api/impact-mr` (`core/mr.py`); recording a single decision against that whole union (rather than per symbol) is the remaining API-model step. The per-minute approve rate limiter is a single-process convenience, not a production control; a multi-worker or multi-host deployment needs an external limit (a reverse proxy or the GitLab webhook rate limit). Precedent matches on the fully-qualified name when one is recorded and otherwise on the exact short symbol name, so a rename is a new identity and would not match a decision made under the old name; tying precedent to a stable symbol id is future work, and an honest one, because Orbit reassigns a definition id on a rename. Reviewer identity is self-asserted in the browser demo unless `KEYSTONE_APPROVE_TOKEN` is set; the GitLab CI gate path binds the actor to a short-lived OIDC token's `sub` claim (`self_asserted=false`) and, when `KEYSTONE_VERIFY_OIDC=1` or a pinned `KEYSTONE_OIDC_JWKS` is set, verifies the token's RS256 signature against the issuer's JWKS (`signature_verified=true`, proven offline in the test suite). The HMAC integrity key lives at `~/.keystone/ledger.key` (or `KEYSTONE_LEDGER_KEY`); back it up, because losing it makes an existing chain unverifiable, and rotating it re-keys only rows written after the change. The public deploy serves a committed real `orbit index` of this repo (status `SNAPSHOT`) with the per-symbol `orbit sql` command shown, rather than a live backend, because no free static host can run one. None of these are hidden in the UI; the status panel always says whether the data is LIVE, SNAPSHOT, or FALLBACK.

## How big is the problem

The wedge is narrow and specific, not a generic TAM: GitLab Ultimate customers who have turned on Orbit Local. Orbit requires Ultimate, so the addressable market is the subset of large-monorepo Ultimate accounts already paying for the knowledge graph and already running merge-request review at a scale where a change can break code nobody in the review owns. For those orgs the onboarding cost is near zero, an MR hook or the committed CI gate that calls the Keystone API on the touched symbols, because the graph they would need is already indexed. The buyer is the platform or CODEOWNERS team accountable for review and for the post-incident write-up. Take the sizing as a disclosed estimate, not a measured market: a 500-engineer org running a few hundred merge requests a week will see a handful of change-failure incidents a quarter (Google's DORA program reports change-failure rates spanning roughly 0 to 15 percent for elite teams and higher for everyone else). If even a few of those each quarter are a silent breaking change to shared code that a blast-radius view would have caught, at tens of engineer-hours each, the recurring cost is real money and real trust, every quarter, per org. That is the wedge Keystone aims at; the precise figure depends on the org and is stated here as an assumption, not a citation.

The reason the wedge widens rather than stays niche is who is writing the merge requests. As AI coding agents move from autocomplete to authoring whole changes, a growing share of MRs are proposed by something that does not carry accountability and cannot be paged at 2am. A human reviewer skimming an agent-authored diff is exactly the moment a silent blast radius slips through, and "an agent approved an agent" is precisely the failure four-eyes exists to stop. Keystone is built for that shift: every decision binds to a verifiable identity, an unregistered or out-of-scope agent cannot self-approve, and the gate refuses an approval that contradicts a recorded human rejection of the same blast radius. The same mechanism that governs a human-authored change governs an agent-authored one, and the second population is the one growing. This is a forward thesis, not a measured market, and it is stated as such, but it is why the addressable set is a floor that rises with agent adoption rather than a fixed slice of today's Ultimate accounts.

## Run it

One command, against the committed real Orbit self-index (the same graph the public deploy uses), with a live `orbit sql` cross-check when the Orbit CLI is present and a real LLM brief + tool-using agent when a free key is in `.env`:

```
./run.ps1            # Windows PowerShell
./run.sh             # macOS / Linux
docker compose up    # container, then open http://127.0.0.1:8787
```

Or by hand: Python 3.11+, `pip install -r requirements.txt`, then `python -m uvicorn backend.app:app --port 8787`. Open http://127.0.0.1:8787 and select a symbol. Run the test suite with `python -m pytest -q`: exact-result blast radius, independent recompute, hash-chain tamper detection, forged-append rejection, epicenter-bound signatures, precedent contradiction strength, cross-namespace precedent, the multi-symbol merge-request union, the agentic tool-loop, the CI OIDC identity binding (including offline RS256 verification), the HTTP API layer, and the skill workflow.

## Deploy a live backend (so a remote judge hits the real product)

The GitHub Pages link is a static snapshot of a real Orbit index. To give a reviewer the live thing — the tool-using agent, the live `orbit sql` cross-check, the real LLM brief — stand up the backend on a free tier. The same `Dockerfile` runs unchanged on any of these and honors the injected `$PORT`:

- Render: `render.yaml` is a one-click Blueprint. render.com → New → Blueprint → connect this repo → Apply.
- Fly.io: `fly launch --copy-config --now` (uses the committed `fly.toml`).
- Any Docker host / Cloud Run: build the `Dockerfile`.

The backend serves the hero same-origin, so the deploy URL is the live demo. Add a free LLM key (`OPENROUTER_API_KEY`, etc.) as a dashboard secret to enable the real AI; without one the live demo runs the deterministic plan. Heads up: a public live backend runs in OPEN MODE (the status panel says so) and the per-instance ledger resets on redeploy; set `KEYSTONE_APPROVE_TOKEN` if you want the gate write-protected.

## Run it on a real Orbit graph

Keystone is not a mock. To point it at a real GitLab Orbit Local graph of any repository:

```
winget install GLab.GLab                 # GitLab CLI (or your platform's package)
glab orbit local --install --yes         # downloads + verifies the Orbit Local binary
glab orbit local index <path-to-a-repo>  # writes ~/.orbit/graph.duckdb
```

Then start Keystone with the Orbit binary wired so the product drives Orbit's own CLI directly (faster and offline; glab adds a per-call network check):

```
# Windows PowerShell
$env:KEYSTONE_ORBIT_BINARY = "$env:LOCALAPPDATA\glab-cli\bin\orbit.exe"
python -m uvicorn backend.app:app --port 8787
```

On startup the status panel flips to `source LIVE` and `orbit CLI+DuckDB`, meaning Keystone ran `orbit schema` and a live `orbit sql` query against the real graph this session, captured in the status transcript. This repository was indexed exactly this way: 262 definitions, 689 relationships, and the engine computes a real blast radius of 12 dependents for its own `compute_blast_radius` function.

Run the governed-review workflow from the command line, which is the Skill's runnable action:

```
python skills/keystone/run_review.py tokenize
python skills/keystone/run_review.py parse --decide approve --reviewer you --reason "reviewed, safe"
```

## Live data versus sample data

The live engine reads a real GitLab Orbit Local graph at `~/.orbit/graph.duckdb` and drives Orbit's own CLI (`orbit schema` and `orbit sql`, the binary `glab orbit local` installs) for live introspection and at least one live query per session. When no live graph is present, Keystone runs on a committed sample fixture and labels the source FALLBACK in the UI. The fixture is built to the exact real Orbit schema (verified against `glab orbit local schema`), so the same engine queries run unchanged on both. A public deployment serves the labeled fixture. Keystone never presents fixture data as live, and the model never produces a displayed number; every figure is computed by the deterministic engine over graph rows.

The web command center is also a self-contained static site, and the public deploy is built over real Orbit data, not a synthetic fixture. `data/keystone_self_graph.duckdb` is a committed real `orbit index` of this very repository (262 definitions). `python scripts/build_static.py` runs the engine over it and precomputes `web/data.json`, and for every reviewable symbol it bakes in the exact `orbit sql` command Orbit itself ran plus the count it returned for that symbol's direct callers (`scripts/capture_orbit_provenance.py` writes `web/orbit_provenance.json`; 120 of 120 symbols cross-verify). So a remote judge who never starts a backend still sees real Orbit numbers next to the real Orbit command that produced them, shown as an "orbit-verified" badge, and the status panel reads `SNAPSHOT` to say plainly that it is a committed real index served without a live server. The headline symbol is `compute_blast_radius`: changing Keystone's own engine lands in the CROSS_TEAM tier and is BLOCKed by a prior identical-blast-signature rejection. The build is deterministic and the CI drift check rebuilds `web/data.json` byte-identically from the committed artifacts, with no Orbit binary or network needed. The frontend tries the live API first and falls back to this bundle; the deployed gate stays interactive and records decisions in the browser only and says so, while the local app persists to the hash-chained ledger.

## How it is built

One core, many shells. A pure-Python engine owns all logic: `core/graph.py` reads the Orbit-shaped DuckDB read-only after introspecting its schema, `core/impact.py` computes the bounded reverse-BFS rings and the blast-radius signature, `core/audit.py` maintains the append-only hash-chained ledger and the deterministic precedent recall, `core/orbit_cli.py` drives the real Orbit CLI. A single FastAPI app serves it. The web command center, the CLI, and the Skill are thin clients of that one core.

The GitLab integration is `skills/keystone/SKILL.md`, an Open Agent Skills definition whose runnable action (`run_review.py`) calls the Keystone API to perform the governed-review workflow, so the artifact automates a specific action rather than chatting.

## What it deliberately does not do

It does not learn or self-evolve; the ledger is memory by recall, never by mutation. It does not let a model recommend or decide a verdict; precedent informs, the human decides. It does not use embeddings or fuzzy matching; precedent matches on exact symbol, owner, and blast signature. Memory proves; it does not pretend.

MIT licensed. See LICENSE.
