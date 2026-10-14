# Life After Code (GitLab Transcend) — Path B build plan

Deadline **Oct 27, 2026 13:00 UTC**. Entry: **Keystone** (`gitlab.com/lalwanivaibhav079/keystone`, MIT, public).

## What already exists (verified, not assumed)

| Asset | State |
|---|---|
| License / visibility | MIT, public on both GitHub and GitLab |
| Tests | `165 passed, 2 skipped` (27.8s) |
| Duo agent | `.gitlab/agents/keystone/agent.yml` — persona, workflow, 6 bound tools |
| MCP server | `mcp/keystone_server.py` — `gate_symbol`, `gate_diff`, `cross_mr_collision`, `scan_repo_and_gate` |
| GitLab CI | 3 stages defined: `test` / `gate` / `deploy` (Pages) |
| Live demo | Render backend + GitHub Pages hero |
| Video | `SUBMISSION/keystone-demo.mp4` (2.06 MB), `keystone-presentation.mp4` (5.14 MB) |

This is not a from-scratch entry. The foundation is strong.

---

## BLOCKER — fix before anything else

**All 20+ GitLab pipelines failed with zero jobs.**

```
pipeline 2618766029  status=failed  jobs=0  duration=null  created_at == updated_at
```

That signature (`0 jobs`, `null duration`, `created == updated`, valid YAML) means **no runner was ever enabled** on the project. The `.gitlab-ci.yml` was never executed even once.

The submission rules state: *"The project's CI/CD pipeline history must be visible and show the automation running."*

Judges will open the pipeline tab. Right now they see 20+ red X's.

**Fix (needs your GitLab account, ~2 minutes):**

1. `gitlab.com/lalwanivaibhav079/keystone` → **Settings → CI/CD → Runners**
2. Enable **GitLab.com Shared Runners** (or register a runner)
3. Push any commit → green pipeline appears

Do this first. Nothing else matters if the pipeline tab is red.

---

## Current lifecycle coverage

The nine stages: `plan / create / verify / package / secure / release / configure / monitor / govern`

| Stage | Coverage | Notes |
|---|---|---|
| **verify** | Strong | Blast radius, cross-MR collisions, MCP gates, CI gate |
| **govern** | Strong | Policy tiers, hash-chained ledger, OIDC + Ed25519 identity |
| **secure** | **Built** | `core/advisory.py` + `scripts/dependency_risk.py`, MCP tools, CI stage |
| **release** | **Built** | `release-gate` CI job fails the pipeline on a propagated BLOCK |
| **package** | **Built** | Scoped lockfile + advisory input; SBOM hash binding still to do |
| **monitor** | Partial | Incident-recall scoring not built yet |
| **configure** | Partial | `core/drift.py` exists, not yet wired into a flow |
| plan / create | None | - |

Three stages moved from none to built in this pass. `configure` and `monitor` remain.

---

## Built in this pass

| Artifact | What it does |
|---|---|
| `core/advisory.py` | The engine. PEP 503 matching, lockfile parsing, import-edge resolution, propagation. Refuses to guess when a version is unpinned or an operator is unsupported. |
| `scripts/dependency_risk.py` | Runnable report plus `--fail-on-block` release gate |
| `scripts/generate_lock.py` | Scoped lockfile generator |
| `data/advisories.example.json` | Six clearly-synthetic `DEMO-*` advisories exercising every branch |
| `data/requirements.lock` | The 12 declared dependencies, pinned |
| `tests/test_advisory.py` | 25 tests: matching, prefix import resolution, ranking, determinism, honest non-matches |
| `.gitlab-ci.yml` | `secure` and `release` stages, 2 new jobs; now 5 stages and 6 jobs |
| `.gitlab/agents/keystone/agent.yml` | 2 new bound tools (6 to 8), supply-chain workflow in the system prompt |

Test suite: **190 passed, 2 skipped** (was 165).

Verified against the real committed self-index. `duckdb` CRITICAL resolves to 2
importing files, 16 definitions, max blast 6, owner `core`, verdict BLOCK.
`fastapi` HIGH resolves to `backend/app.py`, 11 definitions, BLOCK. `starlette`
HIGH is vulnerable but never imported directly, and is reported as 0 entry points
rather than a false all-clear.

### Two problems found and fixed along the way

1. **The lockfile leaked local paths.** A naive `pip freeze` emitted
   `-e c:\users\...\lineage\packages\...`, which would publish the maintainer's
   home directory and an unrelated private project name into a public repo, plus
   488 packages that have nothing to do with this project. Replaced with a scoped
   generator: 12 declared dependencies, zero path leakage.
2. **`agent.yml` was invalid YAML.** The original parsed; an intermediate edit
   dropped `Workflow:` to column 0, which terminated the block scalar. Caught by a
   parse check before commit and rewritten cleanly.

---


## The build: dependency-risk propagation

One engine, four stages. This is the highest-leverage new work because it reuses the machinery that already works rather than bolting on unrelated features.

**Thesis:** when a dependency is flagged vulnerable, or a check fails in production, most tools tell you *a package is bad*. Keystone already computes exact blast radius over the Orbit graph. So it can tell you **which of your symbols, which services, and which teams are actually affected — and gate the release on it.**

### 1. `secure` — CVE → blast radius
- Ingest advisory feeds (OSV / GitHub Advisory) and the resolved dependency lockfile.
- Map each advisory to the packages actually pinned in `requirements.txt`.
- Resolve those packages to owning symbols via `core/impact.py`, then compute the existing bounded reverse-BFS blast radius.
- Output: ranked list of affected symbols + owning teams, not a flat CVE list.

### 2. `package` — SBOM + provenance
- Emit a CycloneDX SBOM from the resolved environment.
- Bind it to the ledger: the SBOM hash is an input to the approval record, so what shipped is provably what was reviewed.
- Reuse `core/attest.py` (already does OIDC-bound attestation) rather than adding a new mechanism.

### 3. `release` — release gating
- New CI stage that refuses a tag/release when the ledger holds an unresolved contradiction or an unadvisory CVE inside the release blast radius.
- Extends the existing `governance-gate` job, which already exits non-zero on BLOCK. Same mechanism, wider trigger.

### 4. `monitor` — incident feedback
- Ingest a production incident (or a failed GitLab check) as a new ledger entry.
- Compute whether the shipped change's recorded blast radius predicted the failure — i.e. **score the engine's own recall against reality.**
- Feeds back into the precedent store, which is what makes the memory get better over time.

The through-line for the write-up: Keystone already refuses to let a model decide. This extends that to the supply chain — the CVE, the SBOM, the release and the incident all have to agree with the ledger before anything ships.

### 5. `configure` — wire drift.py into a flow
`core/drift.py` is written but not in any flow. Expose it as a flow that compares the live configuration against the recorded one and gates on divergence. Cheap, and takes coverage to five.

---

## GitLab Duo Agent Platform surface to register

- **Agent** — publish `.gitlab/agents/keystone/agent.yml` to the AI Catalog, plus a new `dependency-risk` persona.
- **Flow** — the end-to-end chain: *scan → gate → attest → release*, with the incident-recall step closing the loop.
- **MCP server** — `mcp/keystone_server.py` is already an MCP server with four tools. Add `advisory_blast_radius` and `sbom_provenance`.

All three are explicitly named in the rules, so hitting all three matters for both *Technological Implementation* and *Most Stages Covered*.

---

## The post-Oct 5 requirement

Path B requires the agentic automation and the deployment to be **new work done on or after October 5**. Keystone's core is from June. So the submission form must explain what changed during the submission period, and the diff must be real.

The dependency-risk engine above satisfies this cleanly — none of it exists yet, and all of it lands after Oct 5.

---

## Video (<3 min, YouTube, public or unlisted)

Reuse `keystone-demo.mp4` as the spine; it already autoplays the collision → BLOCK → ledger story. New material to cut in:

| Time | Beat |
|---|---|
| 0:00–0:20 | Hook: "A dependency alert doesn't tell you what breaks. Keystone does." |
| 0:20–0:50 | Orin Orbit graph + blast radius (existing footage) |
| 0:50–1:20 | **New:** CVE in a transitive package → affected symbols ranked, teams named |
| 1:20–1:50 | **New:** SBOM bound to the ledger, release gated |
| 1:50–2:20 | **New:** production incident scored against the recorded prediction |
| 2:20–2:50 | Ledger, OIDC attestation, tamper demo (existing footage) |
| 2:50–3:00 | Close |

Judges are not required to watch past 3:00, so the new differentiator has to land before 2:20.

---

## Order of operations

1. **Enable a runner** → push → confirm a green pipeline. *(blocked on your GitLab account)*
2. Register on Devpost (`gitlab-transcend.devpost.com`).
3. Submit GitLab username `lalwanivaibhav079` at `contributors.gitlab.com/transcend-hackathon` → ~24h approval.
4. Build the dependency-risk engine (secure → package → release → monitor).
5. Wire `drift.py` into a flow.
6. Register the agent + flow + MCP server.
7. Deploy (Google Cloud for the +0.2 bonus; GitLab Pages already covered).
8. Record, cut, upload the video.
9. Submit, explaining the post-Oct-5 delta.

Step 3 has ~24h of external latency. Start it now.