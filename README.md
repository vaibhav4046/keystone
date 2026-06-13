# Keystone

[![ci](https://github.com/vaibhav4046/keystone/actions/workflows/ci.yml/badge.svg)](https://github.com/vaibhav4046/keystone/actions/workflows/ci.yml)

Governed change review on the GitLab Orbit code knowledge graph. Keystone shows the real blast radius of a change, requires a human approval with a recorded reason, and keeps a tamper-evident memory that proves it was never edited.

Built for the GitLab Transcend Hackathon, Showcase track.

Live demo: https://vaibhav4046.github.io/keystone/ (the public sample, labeled FALLBACK; the live local-graph run is in the demo video).

## Who it is for, and what breaks today

A staff engineer about to approve a risky refactor needs to see what the change actually touches before they say yes, not after. A platform or CODEOWNERS team enforcing review needs the precedent on a symbol they do not own by heart. A compliance or audit lead, after an incident, has to answer who approved this change, what it touched, and why, from a record nobody could have quietly edited.

Today those questions go unanswered. A merge silently breaks a dozen transitive callers. An approval is recorded with no rationale. A post-incident audit cannot be reconstructed because the log was editable. And increasingly a change proposed by an autonomous coding agent reaches main with no human-auditable gate at all. Keystone is the gate.

Concretely: a ten-person platform team inside a 500-engineer company merges a change to a shared utility that quietly breaks twelve transitive callers; it ships, pages on-call at 2am, and becomes a P2 that burns roughly forty engineer-hours across triage, rollback, and the post-incident review reconstructing who approved what and why. At a loaded 100 dollars an hour that single incident is about four thousand dollars, before the trust cost. Keystone puts the twelve-caller blast radius and the prior rejection in front of the reviewer at the moment of approval, and leaves a record the audit can trust afterward. It is for teams where a change can break code nobody in the review owns; it is not for a solo project where the author already holds the whole graph in their head.

## What it does

Pick a symbol that is about to change. Keystone reads the GitLab Orbit Local code graph and computes the deterministic blast radius: the direct callers, the transitive dependents to a bounded depth, the owning files and directories, ranked as severity rings out from the epicenter. Every number is computed from the graph by a pure-Python engine and is reproducible; the model never invents a figure. A Precedent Panel surfaces prior governance on the same symbol or the same blast signature, including a contradiction when a pending approval conflicts with a past rejection. A reviewer approves or rejects with a written reason, and the decision is appended to an HMAC-keyed, sha256 hash-chained audit ledger whose integrity is recomputed live, showing a green verified badge only when every link checks out.

## Why this is not branch protection, signed commits, or a CI check

Branch protection enforces who clicked approve. Signed commits and GPG git-notes, Sigstore, and in-toto attest who authored or signed code. None of them bind the computed impact of a change and the human rationale and the decision together into one tamper-evident record at the moment of decision, and none surface a contradicting prior rejection while you are about to approve. That binding, plus precedent at the moment of choice, is Keystone. It is complementary to Sigstore and in-toto, not a replacement: they attest the artifact, Keystone attests the decision.

## Integrity model, stated honestly

What the ledger guarantees and what it does not, so the claim is precise rather than marketing:

- Each row's hash is an HMAC over the previous hash plus the canonical payload, keyed by a secret taken from `KEYSTONE_LEDGER_KEY` or generated once and stored outside the repo at `~/.keystone/ledger.key`. Because the key is secret, a party who can read or append to the ledger file still cannot forge a valid tail; recomputing the chain detects both an in-place edit and a forged append. A plain published sha256 chain would not stop a forged append, which is why the HMAC matters. A test (`test_forged_append_with_public_sha256_is_rejected`) proves it.
- Appends are serialised by a process lock, so two concurrent approvals cannot share a previous hash and break the chain. A multi-worker or multi-host deployment needs an external mutex or a database-backed ledger; the single-process server is correct as shipped.
- Reviewer identity is self-asserted unless you set `KEYSTONE_APPROVE_TOKEN`, in which case `POST /api/approve` requires a matching `X-Keystone-Token` header. Binding identity to real GitLab SSO is future work; the README does not claim cryptographic identity it does not have.
- The blast-radius signature is computed over the epicenter plus the sorted affected id set, so two unrelated symbols with no dependents do not collide and produce a phantom contradiction. A prior rejection on the same symbol with a different blast radius is shown as a weaker advisory, not a full contradiction.

## Current limitations

The ledger is a per-instance append-only file: one shared store per deployment, not a multi-tenant service, and a change id maps to a single symbol rather than a multi-symbol merge request. Precedent matches on the fully-qualified name when one is recorded and otherwise on the exact short symbol name, so a rename is a new identity and would not match a decision made under the old name; tying precedent to a stable symbol id is future work. Reviewer identity is self-asserted unless `KEYSTONE_APPROVE_TOKEN` is set; the intended production path is a short-lived GitLab OIDC token with the reviewer taken from the verified `sub` claim, which would replace the shared token. The HMAC integrity key lives at `~/.keystone/ledger.key` (or `KEYSTONE_LEDGER_KEY`); back it up, because losing it makes an existing chain unverifiable, and rotating it re-keys only rows written after the change. The public deploy serves a labeled sample fixture because no free static host can open a local Orbit DuckDB. None of these are hidden in the UI; the status panel always says whether the data is LIVE or FALLBACK.

## How big is the problem

Take it as a disclosed estimate, not a measured market: a 500-engineer org running a few hundred merge requests a week will see a handful of change-failure incidents a quarter (DORA puts elite change-failure rates in the 0 to 15 percent band, and most orgs are not elite). If even a few of those each quarter are a silent breaking change to shared code that a blast-radius view would have caught, at tens of engineer-hours each, the recurring cost is real money and real trust, every quarter, per org. That is the wedge Keystone aims at; the precise figure depends on the org and is stated here as an assumption, not a citation.

## Run it

Requirements: Python 3.11+, then `pip install -r requirements.txt`.

```
python scripts/build_fixture.py          # build the sample graph + seed the ledger
python -m uvicorn backend.app:app --port 8787
```

Open http://127.0.0.1:8787 and select a symbol. Run the test suite with `python -m pytest -q` (32 tests: exact-result blast radius, independent recompute, hash-chain tamper detection, forged-append rejection, epicenter-bound signatures, precedent contradiction strength, and the skill workflow).

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

The web command center is also a self-contained static site. `python scripts/build_static.py` precomputes `web/data.json` from the engine, and the frontend tries the live API first and falls back to that bundle when no backend is reachable. So `web/` deploys to any static host with no server. The committed `.gitlab-ci.yml` runs the tests on every push and publishes the hero to GitLab Pages automatically, so the repository alone yields a green test badge and a live link with no extra accounts. The deployed gate stays interactive; it records decisions in the browser only and says so, while the local app persists to the hash-chained ledger.

## How it is built

One core, many shells. A pure-Python engine owns all logic: `core/graph.py` reads the Orbit-shaped DuckDB read-only after introspecting its schema, `core/impact.py` computes the bounded reverse-BFS rings and the blast-radius signature, `core/audit.py` maintains the append-only hash-chained ledger and the deterministic precedent recall, `core/orbit_cli.py` drives the real Orbit CLI. A single FastAPI app serves it. The web command center, the CLI, and the Skill are thin clients of that one core.

The GitLab integration is `skills/keystone/SKILL.md`, an Open Agent Skills definition whose runnable action (`run_review.py`) calls the Keystone API to perform the governed-review workflow, so the artifact automates a specific action rather than chatting.

## What it deliberately does not do

It does not learn or self-evolve; the ledger is memory by recall, never by mutation. It does not let a model recommend or decide a verdict; precedent informs, the human decides. It does not use embeddings or fuzzy matching; precedent matches on exact symbol, owner, and blast signature. Memory proves; it does not pretend.

MIT licensed. See LICENSE.
