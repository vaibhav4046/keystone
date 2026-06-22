"""Regression tests for the multi-agent audit fixes - pin the contracts so the robustness
defects (corrupt ledger line, scanned-graph type casing, slash branch, reused out_path)
cannot silently come back. All hermetic, no network."""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.audit import Ledger
from core import repo_scan, graph as graph_mod, collision


def _tmp(name: str) -> str:
    return os.path.join(tempfile.mkdtemp(), name)


def test_audit_survives_and_flags_a_corrupt_line():
    led = Ledger(path=_tmp("ledger.jsonl"))
    led.append(actor="a", change_id="c1", target_symbols=["x"], blast_radius_set=[1, 2],
               signature="sig1", decision="approve", rationale="ok")
    led.append(actor="a", change_id="c2", target_symbols=["y"], blast_radius_set=[3],
               signature="sig2", decision="reject", rationale="no")
    assert led.verify()["ok"] is True
    # a truncated/garbage trailing line must NOT crash reads, and verify must flag it
    with open(led.path, "a", encoding="utf-8") as f:
        f.write('{"truncated": \n')
    v = led.verify()
    assert v["ok"] is False and v.get("corrupt") is True
    assert isinstance(led.rows(), list)            # rows() does not raise
    # appending onto a corrupt ledger must be REFUSED, so tamper evidence is never silently
    # overwritten (the round-1 'self-heals' behavior erased evidence - that was the regression).
    import pytest
    with pytest.raises(RuntimeError):
        led.append(actor="a", change_id="c3", target_symbols=["z"], blast_radius_set=[4],
                   signature="sig3", decision="approve", rationale="ok")
    with open(led.path, encoding="utf-8") as f:    # the corrupt bytes are still on disk
        assert "truncated" in f.read()
    assert led.verify()["ok"] is False             # still flagged, not silently healed


def test_scanned_graph_ranks_by_fanin_not_alphabetically():
    # zzz_hub sorts LAST alphabetically but is called by 3 others -> must surface FIRST.
    # (Catches the lowercase definition_type bug that fell back to ORDER BY name.)
    src = {"m.py": (
        "def zzz_hub():\n    return 1\n\n"
        "def caller1():\n    return zzz_hub()\n\n"
        "def caller2():\n    return zzz_hub()\n\n"
        "def caller3():\n    return zzz_hub()\n"
    )}
    p = _tmp("scan.duckdb")
    repo_scan.build_graph_duckdb(src, p, "demo/repo")
    g = graph_mod.Graph(path=p, mode="LIVE")
    names = g.all_definition_names(limit=2)
    assert names[0] == "zzz_hub", names


def test_parse_repo_spec_keeps_slash_branches():
    assert repo_scan.parse_repo_spec("owner/repo/tree/feature/x") == ("owner", "repo", "feature/x")
    assert repo_scan.parse_repo_spec("owner/repo") == ("owner", "repo", "")


def test_build_graph_duckdb_reusable_path():
    p = _tmp("reuse.duckdb")
    src = {"a.py": "def f():\n    return 1\n"}
    repo_scan.build_graph_duckdb(src, p, "demo/repo")
    repo_scan.build_graph_duckdb(src, p, "demo/repo")   # second call on the same path must not crash
    g = graph_mod.Graph(path=p, mode="LIVE")
    assert g.total_definitions() == 1


def _collgraph(src):
    p = _tmp("coll.duckdb")
    repo_scan.build_graph_duckdb(src, p, "demo/repo")
    return graph_mod.Graph(path=p, mode="LIVE")


def test_find_top_collision_is_independent_pair_with_honest_count():
    # x and y are independent (neither calls the other) but are BOTH called by c1/c2/c3,
    # so their shared dependents are exactly {c1,c2,c3} - and must NOT include x or y.
    src = {"m.py": ("def x():\n    return 1\n\ndef y():\n    return 1\n\n"
                    "def c1():\n    return x() + y()\n\ndef c2():\n    return x() + y()\n\n"
                    "def c3():\n    return x() + y()\n")}
    top = collision.find_top_collision(_collgraph(src))
    assert top is not None
    assert {top["a"], top["b"]} == {"x", "y"}
    assert top["kind"] == "blast_overlap"
    assert top["a"] not in top["shared"] and top["b"] not in top["shared"]   # honest count: not the changed symbols
    assert top["shared_count"] == 3 and set(top["shared"]) == {"c1", "c2", "c3"}


def test_find_top_collision_none_and_deterministic():
    assert collision.find_top_collision(_collgraph({"m.py": "def a():\n    return 1\n"})) is None
    g = _collgraph({"m.py": "def x():\n    return 1\n\ndef y():\n    return 1\n\ndef c():\n    return x() + y()\n"})
    assert collision.find_top_collision(g) == collision.find_top_collision(g)   # deterministic


def test_hero_cache_click_reproduces_from_committed_orbit_graph():
    # the served hero number for pallets/click must be REPRODUCIBLE: running find_top_collision on
    # the committed Orbit graph must give the same pair + count a skeptical judge would compute.
    import json
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cache_path = os.path.join(root, "data", "hero_collisions.json")
    graph_path = os.path.join(root, "data", "click_graph.duckdb")
    # Both artifacts are committed (the graph is force-tracked in .gitignore), so this test
    # must EXERCISE the reproduction on every checkout - never silently pass. A missing file
    # here means the headline number is no longer backed by a committed artifact: fail loud.
    assert os.path.exists(graph_path), (
        "committed hero Orbit graph data/click_graph.duckdb is missing - the headline "
        "collision (Parameter x HelpFormatter, 64) must reproduce on a committed artifact")
    assert os.path.exists(cache_path), "data/hero_collisions.json (committed) is missing"
    entry = json.load(open(cache_path, encoding="utf-8")).get("pallets/click")
    assert entry, "hero cache must contain the pallets/click entry"
    top = collision.find_top_collision(graph_mod.Graph(path=graph_path, mode="LIVE"))
    assert top["shared_count"] == entry["collision"]["shared_count"]
    assert {top["a"], top["b"]} == {entry["collision"]["a"], entry["collision"]["b"]}
    assert top["shared_count"] < graph_mod.Graph(path=graph_path, mode="LIVE").total_definitions()


def test_collision_works_on_javascript_sources():
    # multi-language: s1 and s2 are independent JS functions both called by c1/c2/c3
    src = {"a.js": ("function s1(){return 1}\nfunction s2(){return 2}\n"
                    "function c1(){ return s1() + s2(); }\nfunction c2(){ return s1() + s2(); }\n"
                    "function c3(){ return s1() + s2(); }\n")}
    top = collision.find_top_collision(_collgraph(src))
    assert top is not None
    assert {top["a"], top["b"]} == {"s1", "s2"}
    assert set(top["shared"]) == {"c1", "c2", "c3"}


def _name_edges(sources):
    """(set of (caller_name, callee_name) edges, set of def names) for a parsed JS/TS source map."""
    defs, edges = repo_scan._defs_and_edges(sources)
    by_id = {d["id"]: d["name"] for d in defs}
    return {(by_id[s], by_id[t]) for s, t in edges}, {d["name"] for d in defs}


def test_js_call_edges_ignore_comments_and_strings():
    # A callee named only inside a comment, a string, or a template literal must NOT create an
    # edge - that over-attribution would inflate the blast radius the whole product reports.
    src = {"a.js": ("function caller(){\n"
                    "  // target() in a line comment\n"
                    "  /* target() in a block comment */\n"
                    "  const s = \"target()\";\n"
                    "  const t = `target() ${1}`;\n"
                    "  return 1;\n"
                    "}\n"
                    "function target(){ return 2; }\n")}
    edges, names = _name_edges(src)
    assert {"caller", "target"} <= names
    assert ("caller", "target") not in edges      # only mentioned in noise -> no fabricated edge


def test_js_real_call_still_edges_after_stripping():
    # control: a genuine call must still produce its edge once comments/strings are blanked.
    src = {"a.js": ("function caller(){ /* noise */ return target(); }\n"
                    "function target(){ return 2; }\n")}
    edges, names = _name_edges(src)
    assert ("caller", "target") in edges


def test_js_arrow_and_const_functions_resolve():
    src = {"a.js": ("const helper = () => { return 1; };\n"
                    "const caller = () => { return helper(); };\n")}
    edges, names = _name_edges(src)
    assert {"helper", "caller"} <= names
    assert ("caller", "helper") in edges


def test_ts_class_methods_and_type_annotations():
    # class methods resolve to an intra-class edge; TS type names must not become defs or edges.
    src = {"svc.ts": ("class Svc {\n"
                      "  run(id: number): Promise<Thing> { return this.fetchThing(id); }\n"
                      "  fetchThing(id: number): Thing { return null; }\n"
                      "}\n")}
    edges, names = _name_edges(src)
    assert {"run", "fetchThing", "Svc"} <= names
    assert ("run", "fetchThing") in edges
    assert "Promise" not in names and "Thing" not in names   # generics/type refs are not calls


def test_find_definition_and_blast_radius_are_none_safe():
    # find_definition honors its Optional contract on bad input instead of raising; callers that
    # rely on a None return (compute_blast_radius) stay safe.
    from core import impact as impact_mod
    g = _collgraph({"m.py": "def a():\n    return 1\n"})
    assert g.find_definition(None) is None
    assert g.find_definition("") is None
    assert impact_mod.compute_blast_radius(g, None) is None
    assert impact_mod.compute_blast_radius(g, "") is None


def test_js_regex_literal_does_not_swallow_following_code():
    # A quote inside a regex literal (e.g. /["']/g in a .replace) must NOT be read as a string
    # delimiter that blanks all the real code after it - that would DELETE genuine defs + edges.
    src = {"a.js": ("function clean(s){ return s.replace(/[\"']/g, \"\"); }\n"
                    "function caller(){ return clean(x) + helper(); }\n"
                    "function helper(){ return 1; }\n")}
    edges, names = _name_edges(src)
    assert {"clean", "caller", "helper"} <= names              # all defs survive the regex literal
    assert ("caller", "clean") in edges and ("caller", "helper") in edges


def test_strip_js_noise_invariants_and_jsx_safety():
    # length + a JSX close tag must not trigger regex mode (which would eat the following call).
    s = "let a = render(); let b = x</y; let c = helper(); /* note */ const r = /[\"']/.test(a);"
    out = repo_scan._strip_js_noise(s)
    assert len(out) == len(s)                                   # length preserved exactly
    assert s.count("\n") == out.count("\n")                     # newlines preserved
    assert "render(" in out and "helper(" in out               # '</' did not swallow later code
    assert "test(" in out and '"' not in out                   # regex blanked, .test() survives
