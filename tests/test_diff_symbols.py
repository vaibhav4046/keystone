"""MR-diff -> changed-symbols extraction: the autonomous gate runs on a real diff,
not hand-named symbols."""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import fixtures, graph as graph_mod, diff_symbols


def _fixture_graph():
    p = os.path.join(tempfile.mkdtemp(), "fx.duckdb")
    fixtures.build_fixture_duckdb(p)
    return graph_mod.Graph(prefer_live=False)


def test_parse_diff_tracks_new_side_lines():
    diff = ("diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
            "@@ -10,2 +10,3 @@\n ctx\n+added\n ctx2\n")
    # context 'ctx' sits on new-line 10, the added line on 11
    assert diff_symbols.parse_diff(diff) == {"x.py": {11}}
    # a removed line does not consume a new-side line
    diff2 = ("--- a/y.py\n+++ b/y.py\n@@ -5,3 +5,2 @@\n keep\n-gone\n keep2\n")
    assert diff_symbols.parse_diff(diff2) == {}  # only context/removed: no added line recorded


def test_changed_symbols_resolves_a_real_symbol_from_a_diff():
    g = _fixture_graph()
    name, fpath, s, e = g._con.execute(
        "SELECT name, file_path, start_line, end_line FROM gl_definition "
        "WHERE start_line IS NOT NULL ORDER BY (end_line - start_line) DESC LIMIT 1"
    ).fetchone()
    line = int(s) + 1                      # a line strictly inside the definition
    p = str(fpath).lstrip("/")
    diff = (f"diff --git a/{p} b/{p}\n--- a/{p}\n+++ b/{p}\n"
            f"@@ -{line},1 +{line},2 @@\n ctx\n+touched\n")
    syms = diff_symbols.changed_symbols(g, diff)
    assert name in [x["name"] for x in syms], (name, syms)
    # every returned row is fully shaped for the gate
    for x in syms:
        assert {"id", "name", "fqn", "file_path", "definition_type"} <= set(x)
    # a diff touching a file the index does not know yields nothing (no false symbols)
    unknown = ("diff --git a/zzz_not_indexed.py b/zzz_not_indexed.py\n"
               "--- a/zzz_not_indexed.py\n+++ b/zzz_not_indexed.py\n@@ -1 +1,2 @@\n keep\n+x\n")
    assert diff_symbols.changed_symbols(g, unknown) == []
    # an empty diff is empty, not an error
    assert diff_symbols.changed_symbols(g, "") == []
