"""Keystone FastAPI backend: the single owner of business logic.

Imports the pure-Python core (graph, impact, audit) and serves it to every shell.
Serves the static web hero from web/ as well. Every number returned is computed
by the deterministic engine; the LLM and the Orbit CLI are provenance only and
never the source of a displayed figure. Runs fully offline on the fixture.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core import graph as graph_mod, impact as impact_mod
from core.audit import Ledger

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
WEB = os.path.join(ROOT, "web")
LEDGER_PATH = os.path.join(DATA, "audit_ledger.jsonl")

app = FastAPI(title="Keystone", version="1.0.0")

# one shared graph + ledger for the process
_graph = graph_mod.Graph(prefer_live=True)
_ledger = Ledger(LEDGER_PATH)
# seed the ledger if empty so the precedent contradiction is demoable on a cold start
if not os.path.exists(LEDGER_PATH) or os.path.getsize(LEDGER_PATH) == 0:
    from core import fixtures
    for row in fixtures.seed_ledger_rows():
        sig = impact_mod.blast_radius_signature(row["blast_radius_set"])
        _ledger.append(actor=row["actor"], change_id=row["change_id"],
                       target_symbols=row["target_symbols"], blast_radius_set=row["blast_radius_set"],
                       signature=sig, decision=row["decision"], rationale=row["rationale"])


def _orbit_access() -> str:
    return "CLI+DuckDB" if _graph.source.mode == "LIVE" else "FALLBACK"


@app.get("/api/health")
def health():
    return {"ok": True, "service": "keystone", "version": "1.0.0"}


@app.get("/api/status")
def status():
    rep = _graph.schema_report()
    v = _ledger.verify()
    providers = [k for k in ("CEREBRAS_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY")
                 if os.environ.get(k)]
    return {
        "source_mode": rep["mode"],            # LIVE or FALLBACK
        "orbit_access": "CLI+DuckDB" if rep["mode"] == "LIVE" else "DuckDB-fixture",
        "duckdb_path": rep["path"],
        "tables": rep["tables"],
        "schema_pinned": {t: rep["columns"].get(t, []) for t in rep["tables"]},
        "audit_chain": v,                      # {ok, count, broken_index}
        "definitions": _graph.total_definitions(),
        "llm_providers_configured": providers,  # names only, never values
    }


@app.get("/api/definitions")
def definitions():
    return {"names": _graph.all_definition_names()}


@app.get("/api/impact/{name}")
def impact(name: str, max_depth: int = 3):
    imp = impact_mod.compute_blast_radius(_graph, name, max_depth=max_depth)
    if imp is None:
        raise HTTPException(404, f"definition not found: {name}")
    return imp.to_dict()


@app.get("/api/precedent/{name}")
def precedent(name: str, max_depth: int = 3):
    imp = impact_mod.compute_blast_radius(_graph, name, max_depth=max_depth)
    sig = imp.signature if imp else None
    return _ledger.precedent(target_symbols=[name], signature=sig)


@app.get("/api/audit")
def audit():
    return {"rows": _ledger.rows(), "verify": _ledger.verify()}


@app.get("/api/audit/verify")
def audit_verify():
    return _ledger.verify()


class Decision(BaseModel):
    name: str
    decision: str
    reviewer: str
    rationale: str
    max_depth: int = 3


@app.post("/api/approve")
def approve(d: Decision):
    imp = impact_mod.compute_blast_radius(_graph, d.name, max_depth=d.max_depth)
    if imp is None:
        raise HTTPException(404, f"definition not found: {d.name}")
    row = _ledger.append(
        actor=d.reviewer, change_id=f"KS-{d.name}", target_symbols=[d.name],
        blast_radius_set=imp.affected_ids, signature=imp.signature,
        decision=d.decision, rationale=d.rationale,
    )
    return {"row": row, "verify": _ledger.verify()}


# static web hero (mounted last so /api/* wins)
if os.path.isdir(WEB):
    @app.get("/")
    def index():
        return FileResponse(os.path.join(WEB, "index.html"))
    app.mount("/", StaticFiles(directory=WEB), name="web")
