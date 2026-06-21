"""On-the-fly Orbit graph from plain source (zero pre-indexing): the gate runs on a
graph built seconds ago from ast, not a pre-existing Orbit DuckDB. Hermetic (no network)."""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import repo_scan, graph as graph_mod, impact as impact_mod, policy as policy_mod, diff_symbols


def _graph(sources):
    p = os.path.join(tempfile.mkdtemp(), "scan.duckdb")
    repo_scan.build_graph_duckdb(sources, p, "demo/repo")
    return graph_mod.Graph(path=p, mode="LIVE")


def test_parse_repo_spec_handles_urls_and_branches():
    assert repo_scan.parse_repo_spec("pallets/click") == ("pallets", "click", "")
    assert repo_scan.parse_repo_spec("https://github.com/pallets/click.git") == ("pallets", "click", "")
    assert repo_scan.parse_repo_spec("github.com/pallets/click/tree/main") == ("pallets", "click", "main")


def test_on_the_fly_graph_yields_real_blast_radius_and_gate():
    # core() is called by helper() and user() -> 2 direct callers, computed from ast
    g = _graph({
        "a.py": "def core():\n    return 1\n\ndef helper():\n    return core()\n",
        "pkg/b.py": "def user():\n    return core() + helper()\n",
    })
    assert g.total_definitions() == 3
    imp = impact_mod.compute_blast_radius(g, "core")
    assert imp is not None
    callers = g.direct_callers(imp.epicenter_id)
    assert len(callers) == 2                       # helper + user, resolved by ast call edges
    d = imp.to_dict()
    assert d["counts"]["total_affected"] == 2
    pol = policy_mod.evaluate(d)
    assert pol["action"] in ("ALLOW", "HOLD", "BLOCK") and pol["tier"]
    # a symbol nothing calls has an empty blast radius
    leaf = impact_mod.compute_blast_radius(g, "user")
    assert leaf.to_dict()["counts"]["total_affected"] == 0


def test_gate_runs_on_a_diff_against_the_on_the_fly_graph():
    # the autonomous gate (changed-symbols) works on a graph built from source on the fly
    g = _graph({"m.py": "def a():\n    return 1\n\ndef b():\n    return a()\n\ndef c():\n    return a()\n"})
    diff = ("diff --git a/m.py b/m.py\n--- a/m.py\n+++ b/m.py\n"
            "@@ -1,2 +1,3 @@\n def a():\n+    log()\n     return 1\n")
    syms = diff_symbols.changed_symbols(g, diff)
    assert "a" in [s["name"] for s in syms]        # the diff touched a()'s line range
