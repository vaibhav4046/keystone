"""Keystone MCP server.

Exposes the Keystone merge-gate engine as Model Context Protocol tools, so any
MCP-compatible client (Claude Code, Codex, Cursor, Hermes, OpenClaw, Odysseus, ...)
can ask the GitLab Orbit graph for a deterministic ALLOW / HOLD / BLOCK verdict
before it merges - no LLM on the verdict.

Run as a stdio MCP server:
    python mcp/keystone_server.py

Self-test (no MCP client needed):
    python mcp/keystone_server.py --selftest
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core import graph as graph_mod          # noqa: E402
from core import impact as impact_mod        # noqa: E402
from core import policy as policy_mod        # noqa: E402
from core import collision as collision_mod  # noqa: E402
from core import diff_symbols                # noqa: E402
from core import repo_scan                   # noqa: E402
from core import advisory as advisory_mod    # noqa: E402

from mcp.server.fastmcp import FastMCP       # noqa: E402

DEFAULT_GRAPH = os.path.join(ROOT, "data", "keystone_self_graph.duckdb")
DEFAULT_LOCK = os.path.join(ROOT, "data", "requirements.lock")
DEFAULT_ADVISORIES = os.path.join(ROOT, "data", "advisories.example.json")
_RANK = {"ALLOW": 0, "HOLD": 1, "BLOCK": 2}

mcp = FastMCP("keystone")


def _graph(graph_path: str = ""):
    return graph_mod.Graph(path=(graph_path or DEFAULT_GRAPH), mode="LIVE")


def _gate_one(g, symbol: str):
    imp = impact_mod.compute_blast_radius(g, symbol)
    if imp is None:
        return None
    d = imp.to_dict()
    pol = policy_mod.evaluate(d)
    return {"symbol": symbol, "blast_radius": d["counts"]["total_affected"],
            "tier": pol.get("tier"), "action": pol.get("action"),
            "required_approvers": pol.get("required_approvers"),
            "reasons": pol.get("reasons", [])}


def gate_symbol(symbol: str, graph_path: str = "") -> dict:
    """Gate a change to ONE symbol. Returns its blast radius and a deterministic
    ALLOW / HOLD / BLOCK verdict computed from the GitLab Orbit call graph (no LLM).

    symbol: the function/class/definition name being changed.
    graph_path: optional path to an Orbit DuckDB graph; defaults to Keystone's self-index.
    """
    g = _graph(graph_path)
    out = _gate_one(g, symbol)
    if out is None:
        return {"ok": False, "error": "symbol_not_found", "symbol": symbol}
    out["ok"] = True
    return out


def gate_diff(unified_diff: str, graph_path: str = "") -> dict:
    """Gate a unified diff. Extracts the changed symbols by line range and returns a
    per-symbol verdict plus an overall verdict (the strictest). Deterministic, no LLM.
    """
    g = _graph(graph_path)
    changed = diff_symbols.changed_symbols(g, unified_diff)
    results, worst = [], "ALLOW"
    for s in changed:
        out = _gate_one(g, s["name"])
        if out is None:
            continue
        results.append(out)
        if _RANK.get(out["action"], 0) > _RANK.get(worst, 0):
            worst = out["action"]
    return {"ok": True, "changed": results, "verdict": worst}


def cross_mr_collision(symbols_a: list, symbols_b: list, graph_path: str = "") -> dict:
    """Detect a cross-MR blast collision: do two merge requests, each changing a set of
    symbols, share runtime dependents that would break together even with no Git conflict?
    Returns the collision packet (shared dependents, merge order) or no-collision.
    """
    g = _graph(graph_path)
    out = collision_mod.detect_collisions(
        g, [{"id": "MR-A", "symbols": list(symbols_a)},
            {"id": "MR-B", "symbols": list(symbols_b)}])
    if not out:
        return {"ok": True, "collision": False,
                "note": "No shared runtime dependents - safe to merge in any order."}
    out["ok"] = True
    return out


def scan_repo_and_gate(repo: str, github_token: str = "", top: int = 8) -> dict:
    """Build the Orbit graph for ANY public repo on the fly (zero pre-indexing) and gate
    its highest-blast-radius symbols. repo is 'owner/repo' or a GitHub URL. Optional
    github_token raises the API rate limit. Deterministic, no LLM.
    """
    g, stats = repo_scan.scan_repo(repo, token=(github_token or None))
    scored = []
    for name in g.all_definition_names(limit=400):
        out = _gate_one(g, name)
        if out is not None:
            scored.append(out)
    scored.sort(key=lambda x: -x["blast_radius"])
    return {"ok": True, "repo": stats["repo"], "definitions": stats["definitions"],
            "top": scored[: max(1, min(int(top), 50))]}


def advisory_exposure(package: str, advisories_path: str = "", lock_path: str = "",
                      graph_path: str = "") -> dict:
    """Turn a package advisory into a ranked blast radius over the Orbit graph.

    A scanner tells you `package X has a CVE`. This tells you which of THIS repo's
    definitions import it, how far the damage travels from each, and which
    directory owns the blast -- which is the question you actually have to act on.

    package: advisory id (GHSA-/CVE-/DEMO-) or the package name itself.
    advisories_path: local JSON advisories; defaults to the shipped example set.
    lock_path: pinned requirements; defaults to data/requirements.lock.
    Deterministic: no network call, no LLM, identical inputs give identical output.
    """
    advs = advisory_mod.load_advisories(advisories_path or DEFAULT_ADVISORIES)
    if not advs:
        return {"ok": False, "error": "no_advisories",
                "advisories_path": advisories_path or DEFAULT_ADVISORIES}
    locked = advisory_mod.parse_requirements(lock_path or DEFAULT_LOCK)

    norm = package.strip().lower()
    picked = [a for a in advs
              if a.id.lower() == norm or a.norm_package == advisory_mod.normalize_package(package)]
    if not picked:
        return {"ok": False, "error": "advisory_not_found", "query": package,
                "available": sorted(a.id for a in advs)}

    g = _graph(graph_path)
    out = [advisory_mod.propagate(g, a, locked).to_dict() for a in picked]
    g.close()
    return {"ok": True, "query": package, "exposures": out,
            "worst_verdict": max((e["verdict"] for e in out), key=lambda v: _RANK.get(v, 0))}


def dependency_risk(advisories_path: str = "", lock_path: str = "",
                    graph_path: str = "") -> dict:
    """Run every known advisory through dependency-risk propagation and return the
    ranked report, worst first. This is the `secure` stage entry point: it is what
    gates a release.

    Advisories are read from a local file, never the network, so CI and a judge's
    re-run produce byte-identical output and a flaky advisory feed cannot move a gate.
    """
    advs = advisory_mod.load_advisories(advisories_path or DEFAULT_ADVISORIES)
    locked = advisory_mod.parse_requirements(lock_path or DEFAULT_LOCK)
    if not advs:
        return {"ok": False, "error": "no_advisories", "exposures": []}
    g = _graph(graph_path)
    rows = [e.to_dict() for e in advisory_mod.propagate_all(g, advs, locked)]
    g.close()
    return {
        "ok": True,
        "advisories": len(rows),
        "matched": sum(1 for r in rows if r["matched"]),
        "blocked": sum(1 for r in rows if r["verdict"] == "BLOCK"),
        "verdict": max((r["verdict"] for r in rows), key=lambda v: _RANK.get(v, 0)) if rows else "ALLOW",
        "exposures": rows,
    }


for _fn in (gate_symbol, gate_diff, cross_mr_collision, scan_repo_and_gate,
            advisory_exposure, dependency_risk):
    mcp.tool()(_fn)


def _selftest() -> int:
    import json
    print("gate_symbol(compute_blast_radius):")
    print(json.dumps(gate_symbol("compute_blast_radius"), indent=2))
    print("\ngate_diff(touch compute_blast_radius):")
    diff = ("diff --git a/core/impact.py b/core/impact.py\n--- a/core/impact.py\n"
            "+++ b/core/impact.py\n@@ -97,3 +97,4 @@\n def compute_blast_radius(graph, target_name):\n"
            "+    log()\n     pass\n")
    print(json.dumps(gate_diff(diff), indent=2)[:600])
    print("\ncross_mr_collision([compute_blast_radius],[verify]):")
    print(json.dumps(cross_mr_collision(["compute_blast_radius"], ["verify"]), indent=2)[:600])
    print("\nadvisory_exposure(DEMO-0002):")
    print(json.dumps(advisory_exposure("DEMO-0002"), indent=2)[:900])
    print("\ndependency_risk():")
    r = dependency_risk()
    print(json.dumps({k: v for k, v in r.items() if k != "exposures"}, indent=2))
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    mcp.run()
