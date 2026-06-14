"""Keystone FastAPI backend: the single owner of business logic.

Imports the pure-Python core (graph, impact, audit) and serves it to every shell.
Serves the static web hero from web/ as well. Every number returned is computed
by the deterministic engine; the LLM and the Orbit CLI are provenance only and
never the source of a displayed figure. Runs fully offline on the fixture.
"""
from __future__ import annotations

import datetime
import hmac
import os
import sys
import threading
import time
from contextlib import asynccontextmanager
from typing import Literal, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI, HTTPException, Header, Path, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core import (graph as graph_mod, impact as impact_mod, orbit_cli,
                  policy as policy_mod, attest as attest_mod, agents as agents_mod, gate as gate_mod,
                  llm as llm_mod, agent as agent_mod, mr as mr_mod, collision as collision_mod,
                  graph_audit as graph_audit_mod)
from core.audit import Ledger

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
WEB = os.path.join(ROOT, "web")
# Env overrides keep the app testable in-process: KEYSTONE_LEDGER_PATH points the
# ledger at a temp file, KEYSTONE_PREFER_LIVE=0 forces the committed fixture.
LEDGER_PATH = os.environ.get("KEYSTONE_LEDGER_PATH") or os.path.join(DATA, "audit_ledger.jsonl")
_PREFER_LIVE = os.environ.get("KEYSTONE_PREFER_LIVE", "1") != "0"

# Optional shared secret for the approval gate. When set, POST /api/approve requires
# a matching X-Keystone-Token header, so a decision cannot be recorded by an
# arbitrary client. Unset means open (single-user local demo); the README integrity
# note states identity is self-asserted unless this is configured.
APPROVE_TOKEN = os.environ.get("KEYSTONE_APPROVE_TOKEN")
# A policy-BLOCK override is a privileged action: when this is set it must be
# separately credentialed (X-Keystone-Override-Token), not the shared approve token.
OVERRIDE_TOKEN = os.environ.get("KEYSTONE_OVERRIDE_TOKEN")
MAX_DEPTH_CAP = 8


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    try:
        _graph.close()
    except Exception:
        pass


app = FastAPI(title="Keystone", version="1.0.0", lifespan=lifespan)

# No-auth + same-origin demo: lock CORS to the local origins the hero is served on,
# so even if the backend is exposed beyond localhost an arbitrary site cannot POST a
# decision (CSRF). Override with KEYSTONE_CORS_ORIGINS (comma-separated) if needed.
_origins = os.environ.get("KEYSTONE_CORS_ORIGINS",
                          "http://127.0.0.1:8787,http://localhost:8787").split(",")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in _origins if o.strip()],
                   allow_methods=["GET", "POST"], allow_headers=["*"])

# one shared graph + ledger for the process. KEYSTONE_GRAPH_PATH lets the one-command
# launcher point the backend at the committed real self-index (data/keystone_self_graph.duckdb)
# so a local demo shows the SAME real Orbit graph as the public deploy, in LIVE mode with a
# live `orbit sql` cross-check; unset falls back to ~/.orbit -> fixture.
_GRAPH_PATH = os.environ.get("KEYSTONE_GRAPH_PATH")
if _GRAPH_PATH and graph_mod._is_valid_duckdb(_GRAPH_PATH):
    _graph = graph_mod.Graph(path=_GRAPH_PATH, mode="LIVE")
else:
    _graph = graph_mod.Graph(prefer_live=_PREFER_LIVE)
_ledger = Ledger(LEDGER_PATH)

# When running on a LIVE Orbit graph and glab is resolvable, drive Orbit's OWN CLI
# once at startup (schema introspection + one live query) so the product genuinely
# exercises Orbit's published interface, not just a DuckDB file read. The captured
# transcript feeds /status; the engine's numbers still come from core/impact.py.
_orbit_cli_ok = False
if _graph.source.mode == "LIVE" and orbit_cli.cli_available():
    try:
        orbit_cli.schema()                 # live `glab orbit local schema`
        _orbit_cli_ok = orbit_cli.probe().ok  # live `glab orbit local sql "SELECT ..."`
    except Exception:
        _orbit_cli_ok = False
# seed the ledger if empty so the precedent contradiction is demoable on a cold start.
# Adaptive: scripted tokenize/parse story on the fixture, or a real prior decision on
# the most-depended-on live symbol when running on an indexed Orbit graph.
if not os.path.exists(LEDGER_PATH) or os.path.getsize(LEDGER_PATH) == 0:
    from core import seed as seed_mod
    for row in seed_mod.seed_rows_for(_graph):
        sig = impact_mod.blast_radius_signature(row["blast_radius_set"], row.get("epicenter_id"))
        _ledger.append(actor=row["actor"], change_id=row["change_id"],
                       target_symbols=row["target_symbols"], blast_radius_set=row["blast_radius_set"],
                       signature=sig, decision=row["decision"], rationale=row["rationale"],
                       extra={"seeded": True})   # historical precedent, excluded from live quorum counts


if APPROVE_TOKEN is None:
    print("KEYSTONE: OPEN MODE - no KEYSTONE_APPROVE_TOKEN set; any reachable caller can "
          "record decisions. Set KEYSTONE_APPROVE_TOKEN (and KEYSTONE_OVERRIDE_TOKEN) for a gated deployment.",
          file=sys.stderr)


def _orbit_access() -> str:
    """Honest label: only claim CLI when the CLI actually ran this session."""
    if _graph.source.mode != "LIVE":
        return "FALLBACK"
    return "CLI+DuckDB" if _orbit_cli_ok else "DuckDB"


@app.get("/api/health")
def health():
    return {"ok": True, "service": "keystone", "version": "1.0.0"}


def _orbit_crosscheck(epi_id: int) -> Optional[dict]:
    """Make the Orbit CLI load-bearing for a displayed figure: independently count
    the epicenter's direct callers via `orbit sql` and compare to the engine's
    ring-1. The engine remains the source of truth; this is a live cross-check that
    proves the number came from a real Orbit query, surfaced as an orbit-verified
    badge. Never raises; returns None when the CLI is unavailable."""
    if not _orbit_cli_ok:
        return None
    try:
        # Mirror the engine's ring-1 semantics EXACTLY (core/graph.direct_callers): DISTINCT
        # source definitions, self-edges excluded. A raw count(*) over-counts duplicate/self
        # CALLS edges and would make the live cross-check spuriously differ from the engine.
        q = ("SELECT count(DISTINCT source_id) AS n FROM gl_edge WHERE target_id = {} "
             "AND relationship_kind='CALLS' AND source_kind='Definition' AND target_kind='Definition' "
             "AND source_id <> target_id").format(int(epi_id))
        res = orbit_cli.sql(q)
        if not res.ok:
            return None
        n = None
        parsed = res.parsed                      # structured rows from orbit_cli._parse_rows
        if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
            for val in parsed[0].values():
                s = str(val).strip()
                if s.isdigit():
                    n = int(s); break
        if n is None:                            # robust fallback: last integer token
            import re as _re
            m = _re.findall(r"\d+", res.stdout or "")
            n = int(m[-1]) if m else None
        return {"ring1_cli": n, "command": res.command, "ok": n is not None}
    except Exception:
        return None


@app.get("/api/status")
def status():
    rep = _graph.schema_report()
    v = _ledger.verify()
    return {
        "source_mode": rep["mode"],            # LIVE or FALLBACK
        "orbit_access": _orbit_access(),       # CLI+DuckDB / DuckDB / FALLBACK (honest)
        "duckdb_path": rep["path"],
        "repo": _graph.repo_label(),
        "tables": rep["tables"],
        "schema_pinned": {t: rep["columns"].get(t, []) for t in rep["tables"]},
        "audit_chain": v,                      # {ok, count, broken_index}
        "definitions": _graph.total_definitions(),
        "orbit_cli_transcript": orbit_cli.get_transcript(limit=6),  # proves the CLI ran
        "integrity": {"hmac": True, "approve_token_required": APPROVE_TOKEN is not None,
                      # honest: a token proves possession, not identity. Cryptographic
                      # identity binding (GitLab OIDC sub claim) is future work.
                      "reviewer_verified": False,
                      # fail-loud: no token => any reachable caller can record decisions
                      "open_mode": APPROVE_TOKEN is None,
                      "override_token_required": OVERRIDE_TOKEN is not None},
        "window_enforced": bool(policy_mod.load_policy().get("window_enforced")),
        "llm_providers": llm_mod.available_providers(),   # names only; brief is AI when present, else deterministic
    }


@app.get("/api/definitions")
def definitions():
    return {"names": _graph.all_definition_names()}


def _impact_with_governance(name: str, max_depth: int):
    """Shared: compute impact, the precedent, and the deterministic policy/tier
    decision the Orbit blast radius drives. Returns (imp, dict) or (None, None)."""
    imp = impact_mod.compute_blast_radius(_graph, name, max_depth=max_depth)
    if imp is None:
        return None, None
    out = imp.to_dict()
    prec = _ledger.precedent(target_symbols=[name], signature=imp.signature,
                             target_fqns=[imp.epicenter_fqn] if imp.epicenter_fqn else None)
    pol = policy_mod.evaluate(out, prec)
    out["policy"] = pol                                   # tier / action / required approvers / reasons
    out["orbit_snapshot_sha256"] = attest_mod.orbit_snapshot_sha256(out)
    cross = _orbit_crosscheck(imp.epicenter_id)
    if cross is not None:
        cross["ring1_engine"] = imp.counts.get("ring_1", 0)
        cross["match"] = cross.get("ring1_cli") == cross["ring1_engine"]
        out["orbit_crosscheck"] = cross
    return imp, out


@app.get("/api/impact/{name}")
def impact(name: str = Path(max_length=256), max_depth: int = Query(default=3, ge=1, le=MAX_DEPTH_CAP)):
    _imp, out = _impact_with_governance(name, max_depth)
    if out is None:
        raise HTTPException(404, f"definition not found: {name}")
    return out


@app.get("/api/brief/{name}")
def brief(name: str = Path(max_length=256)):
    """A natural-language governed-review brief. REAL AI when a free LLM key has
    quota (provider named), else a deterministic template (clearly labeled). The
    model only explains the engine's facts; it never produces a number or a verdict."""
    _imp, out = _impact_with_governance(name, 3)
    if out is None:
        raise HTTPException(404, f"definition not found: {name}")
    epi = out.get("epicenter", {})
    prec = _ledger.precedent(target_symbols=[name], signature=out["signature"],
                             target_fqns=[epi.get("fqn")] if epi.get("fqn") else None)
    pol = out["policy"]
    ctx = {"symbol": name, "fqn": epi.get("fqn"), "file": epi.get("file"),
           "counts": pol["counts"], "tier": pol["tier"], "action": pol["action"],
           "required_approvers": pol["required_approvers"], "precedent": prec, "signature": out["signature"]}
    res = llm_mod.review_brief(ctx)
    res["providers_configured"] = llm_mod.available_providers()
    return res


class MRQuery(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=40)
    max_depth: int = Field(default=3, ge=1, le=MAX_DEPTH_CAP)


@app.post("/api/impact-mr")
def impact_mr(q: MRQuery):
    """The MR-level blast radius: the UNION across every symbol a merge request touches,
    with the STRICTEST governance tier applied (core/mr.py). A real MR edits several
    symbols; this is the conservative composition the single-symbol endpoint can't express."""
    clean = [s for s in (x.strip() for x in q.symbols) if s][:40]
    out = mr_mod.compute_mr_impact(_graph, clean, max_depth=q.max_depth)
    if out is None:
        raise HTTPException(404, "none of the given symbols were found in the graph")
    return out


class MROpen(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    symbols: list[str] = Field(min_length=1, max_length=40)


class CollisionQuery(BaseModel):
    mrs: list[MROpen] = Field(min_length=1, max_length=20)
    max_depth: int = Field(default=3, ge=1, le=MAX_DEPTH_CAP)


@app.post("/api/collisions")
def collisions(q: CollisionQuery):
    """Cross-MR blast-collision detection (core/collision.py): given several OPEN merge
    requests, find where their blast radii collide on the Orbit call graph — the semantic
    merge hazard that has NO textual conflict, so Git and GitLab are blind to it — and
    propose a safe merge order. Pure deterministic graph computation; reveals a capability
    the standard review surface does not."""
    out = collision_mod.detect_collisions(
        _graph, [{"id": m.id, "symbols": m.symbols} for m in q.mrs], max_depth=q.max_depth)
    if out is None:
        raise HTTPException(404, "none of the MRs' symbols were found in the graph")
    return out


@app.get("/api/graph-audit")
def graph_audit(limit: int = Query(default=14, ge=1, le=50)):
    """Review-debt hazard (core/graph_audit.py): high-blast symbols that NO test file
    directly exercises in the Orbit call graph — a change that is both high-impact and
    unverified. The second graph-revealed hazard the standard review surface hides."""
    return graph_audit_mod.review_debt_report(_graph, limit=limit)


class AssistantQuery(BaseModel):
    symbol: str = Field(min_length=1, max_length=256)
    question: Optional[str] = Field(default=None, max_length=400)


@app.post("/api/assistant")
def assistant(q: AssistantQuery):
    """Run the bounded tool-using review assistant (core/agent.py). REAL agent loop when a
    free LLM key has quota: the model calls deterministic engine tools (blast_radius,
    precedent, propose_reviewers) and returns a recommendation + the tool trace. Falls back
    to a deterministic plan. The assistant PROPOSES; it never records a decision."""
    if impact_mod.compute_blast_radius(_graph, q.symbol, max_depth=3) is None:
        raise HTTPException(404, f"definition not found: {q.symbol}")
    res = agent_mod.run_agent(_graph, _ledger, q.symbol, q.question)
    res["providers_configured"] = llm_mod.available_providers()
    return res


@app.get("/api/policy")
def policy():
    p = policy_mod.load_policy()
    return {"policy": p, "policy_hash": policy_mod.policy_hash(p)}


@app.get("/api/agent-scope/{name}")
def agent_scope(name: str = Path(max_length=256), author: str = Query(...), kind: str = Query(default="agent")):
    _imp, out = _impact_with_governance(name, 3)
    if out is None:
        raise HTTPException(404, f"definition not found: {name}")
    ctx = agents_mod.resolve_author(author, declared_kind=kind)
    return {"author": ctx, "scope_check": agents_mod.check_scope(ctx, out)}


@app.get("/api/precedent/{name}")
def precedent(name: str = Path(max_length=256), max_depth: int = Query(default=3, ge=1, le=MAX_DEPTH_CAP)):
    imp = impact_mod.compute_blast_radius(_graph, name, max_depth=max_depth)
    sig = imp.signature if imp else None
    fqns = [imp.epicenter_fqn] if (imp and imp.epicenter_fqn) else None
    return _ledger.precedent(target_symbols=[name], signature=sig, target_fqns=fqns)


@app.get("/api/audit")
def audit():
    return {"rows": _ledger.rows(), "verify": _ledger.verify()}


@app.get("/api/audit/verify")
def audit_verify():
    return _ledger.verify()


class Decision(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    decision: Literal["approve", "reject"]
    reviewer: str = Field(min_length=1, max_length=120)
    rationale: str = Field(min_length=1, max_length=2048)
    change_id: Optional[str] = Field(default=None, max_length=120)  # the MR/change id; quorum is per change_id
    change_author: Optional[str] = Field(default=None, max_length=120)  # who proposed the change (four-eyes)
    author_kind: Optional[str] = Field(default=None, max_length=16)  # "agent" enforces an agent scope manifest
    override: bool = False                                            # accountable override of a policy BLOCK
    max_depth: int = Field(default=3, ge=1, le=MAX_DEPTH_CAP)


# Simple in-process per-minute limiter on the only state-mutating endpoint, so a
# loop cannot flood the ledger (each row makes contradiction recall O(n)).
_RATE = {"window": 0, "count": 0}
_RATE_LOCK = threading.Lock()
_RATE_MAX_PER_MIN = int(os.environ.get("KEYSTONE_APPROVE_RATE_PER_MIN", "30"))


def _rate_ok() -> bool:
    now = int(time.time() // 60)
    with _RATE_LOCK:
        if now != _RATE["window"]:
            _RATE["window"] = now
            _RATE["count"] = 0
        _RATE["count"] += 1
        return _RATE["count"] <= _RATE_MAX_PER_MIN


@app.post("/api/approve")
def approve(d: Decision, x_keystone_token: Optional[str] = Header(default=None),
            x_keystone_override_token: Optional[str] = Header(default=None)):
    if APPROVE_TOKEN is not None and not hmac.compare_digest(x_keystone_token or "", APPROVE_TOKEN):
        raise HTTPException(401, "invalid or missing X-Keystone-Token")  # constant-time compare
    if d.override and OVERRIDE_TOKEN is not None and not hmac.compare_digest(x_keystone_override_token or "", OVERRIDE_TOKEN):
        raise HTTPException(401, "override requires a valid X-Keystone-Override-Token")
    if not _rate_ok():
        raise HTTPException(429, "too many approvals; slow down")
    # one shared enforcement decision (identical to the CLI gate, core/gate.py)
    res = gate_mod.evaluate(_graph, _ledger, name=d.name, decision=d.decision, reviewer=d.reviewer,
                            change_id=d.change_id, change_author=d.change_author, author_kind=d.author_kind,
                            override=d.override, max_depth=d.max_depth)
    if not res["ok"]:
        raise HTTPException(res["status"], res.get("detail") or res["error"])

    sig, change_id, pol, out = res["sig"], res["change_id"], res["policy"], res["impact"]
    row = _ledger.append(
        actor=d.reviewer, change_id=change_id, target_symbols=[d.name], target_fqns=res["target_fqns"],
        blast_radius_set=res["blast_set"], signature=sig, decision=d.decision, rationale=d.rationale,
        extra=res["row_extra"],
        ts=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),  # real time, not fixture
    )
    att = attest_mod.build_attestation(impact_dict=out, policy_eval=pol, row=row, source_mode=_graph.source.mode)
    return {"row": row, "verify": _ledger.verify(), "policy": pol, "author": res["author"],
            "self_asserted": res.get("self_asserted", True),
            "quorum": {k: res["quorum"][k] for k in ("required", "confirmed", "status", "closed")},
            "attestation": att}


@app.get("/api/attestation/{name}")
def attestation(name: str = Path(max_length=256)):
    _imp, out = _impact_with_governance(name, 3)
    if out is None:
        raise HTTPException(404, f"definition not found: {name}")
    rows = [r for r in _ledger.rows() if name in (r.get("target_symbols") or [])]
    if not rows:
        raise HTTPException(404, f"no recorded decision for {name}")
    att = attest_mod.build_attestation(impact_dict=out, policy_eval=out["policy"],
                                       row=rows[0], source_mode=_graph.source.mode)
    return {"attestation": att, "verify": attest_mod.verify_attestation(att, _ledger)}


# static web hero (mounted last so /api/* wins)
if os.path.isdir(WEB):
    @app.get("/")
    def index():
        return FileResponse(os.path.join(WEB, "index.html"))
    app.mount("/", StaticFiles(directory=WEB), name="web")
