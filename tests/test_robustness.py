"""Regression tests for the multi-agent audit fixes - pin the contracts so the robustness
defects (corrupt ledger line, scanned-graph type casing, slash branch, reused out_path)
cannot silently come back. All hermetic, no network."""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.audit import Ledger
from core import repo_scan, graph as graph_mod


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
    assert v["ok"] is False
    assert isinstance(led.rows(), list)            # rows() does not raise
    # the atomic rewrite on the next append drops the corrupt line and re-validates the chain
    led.append(actor="a", change_id="c3", target_symbols=["z"], blast_radius_set=[4],
               signature="sig3", decision="approve", rationale="ok")
    assert led.verify()["ok"] is True


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
