# Keystone

Governed change review on the GitLab Orbit code knowledge graph. Keystone shows the real blast radius of a change, requires a human approval with a recorded reason, and keeps a tamper-evident memory that proves it was never edited.

Built for the GitLab Transcend Hackathon, Showcase track.

## Who it is for, and what breaks today

A staff engineer about to approve a risky refactor needs to see what the change actually touches before they say yes, not after. A platform or CODEOWNERS team enforcing review needs the precedent on a symbol they do not own by heart. A compliance or audit lead, after an incident, has to answer who approved this change, what it touched, and why, from a record nobody could have quietly edited.

Today those questions go unanswered. A merge silently breaks a dozen transitive callers. An approval is recorded with no rationale. A post-incident audit cannot be reconstructed because the log was editable. And increasingly a change proposed by an autonomous coding agent reaches main with no human-auditable gate at all. Keystone is the gate.

## What it does

Pick a symbol that is about to change. Keystone reads the GitLab Orbit Local code graph and computes the deterministic blast radius: the direct callers, the transitive dependents to a bounded depth, the owning files and directories, ranked as severity rings out from the epicenter. Every number is computed from the graph by a pure-Python engine and is reproducible; the model never invents a figure. A Precedent Panel surfaces prior governance on the same symbol or the same blast signature, including a contradiction when a pending approval conflicts with a past rejection. A reviewer approves or rejects with a written reason, and the decision is appended to a sha256 hash-chained audit ledger whose integrity is recomputed live, showing a green verified badge only when every link checks out.

## Why this is not branch protection, signed commits, or a CI check

Branch protection enforces who clicked approve. Signed commits and GPG git-notes, Sigstore, and in-toto attest who authored or signed code. None of them bind the computed impact of a change and the human rationale and the decision together into one tamper-evident record at the moment of decision, and none surface a contradicting prior rejection while you are about to approve. That binding, plus precedent at the moment of choice, is Keystone.

## Run it

Requirements: Python 3.11+, then `pip install duckdb fastapi "uvicorn[standard]"`.

```
python scripts/build_fixture.py          # build the sample graph + seed the ledger
python -m uvicorn backend.app:app --port 8787
```

Open http://127.0.0.1:8787 and select a symbol. Run the test suite with `python -m pytest -q` (28 tests: exact-result blast radius, independent recompute, hash-chain tamper detection, precedent contradiction, and the skill workflow).

Run the governed-review workflow from the command line, which is the Skill's runnable action:

```
python skills/keystone/run_review.py tokenize
python skills/keystone/run_review.py parse --decide approve --reviewer you --reason "reviewed, safe"
```

## Live data versus sample data

The live engine reads a real GitLab Orbit Local graph at `~/.orbit/graph.duckdb` and drives Orbit's own CLI (`glab orbit local schema` and `glab orbit local sql`) for live introspection and queries. When no live graph is present, Keystone runs on a committed sample fixture and labels the source FALLBACK in the UI. A public deployment serves that labeled fixture; the live local-graph run is shown in the demo video. Keystone never presents fixture data as live.

The web command center is also a self-contained static site. `python scripts/build_static.py` precomputes `web/data.json` from the engine, and the frontend tries the live API first and falls back to that bundle when no backend is reachable. So `web/` deploys to any static host with no server: `npx wrangler pages deploy web` (Cloudflare Pages), or commit `web/` as a GitLab Pages artifact. The deployed gate stays interactive; it records decisions in the browser only and says so, while the local app persists to the hash-chained ledger.

## How it is built

One core, many shells. A pure-Python engine owns all logic: `core/graph.py` reads the Orbit-shaped DuckDB read-only after introspecting its schema, `core/impact.py` computes the bounded reverse-BFS rings and the blast-radius signature, `core/audit.py` maintains the append-only hash-chained ledger and the deterministic precedent recall, `core/orbit_cli.py` drives the real Orbit CLI. A single FastAPI app serves it. The web command center, the CLI, and the Skill are thin clients of that one core.

The GitLab integration is `skills/keystone/SKILL.md`, an Open Agent Skills definition whose runnable action (`run_review.py`) calls the Keystone API to perform the governed-review workflow, so the artifact automates a specific action rather than chatting.

## What it deliberately does not do

It does not learn or self-evolve; the ledger is memory by recall, never by mutation. It does not let a model recommend or decide a verdict; precedent informs, the human decides. It does not use embeddings or fuzzy matching; precedent matches on exact symbol, owner, and blast signature. Memory proves; it does not pretend.

MIT licensed. See LICENSE.
