"""Committed deterministic fixture graph and seeded audit ledger.

Keystone's live engine reads a real GitLab Orbit Local DuckDB. When that file is
absent or invalid (for example before the Day-1 Orbit spike has produced one),
the engine falls back to THIS committed fixture so the whole product, its tests,
and a cold-clicked public deploy still work. The fixture is shaped like the
Orbit Local schema (gl_directory, gl_file, gl_definition, gl_edge) so the same
queries run against it unchanged.

The fixture models a small parser hot path so blast-radius counts are knowable
and asserted in tests. Edge semantics: an edge (src -> dst, type 'calls') means
src CALLS dst, so the blast radius of changing a target T is everything that
DEPENDS ON T, found by walking edges in REVERSE from T (callers, then callers of
callers). Nothing here is random; ids and rows are fixed.

Standard library plus duckdb only. No web imports, no LLM.
"""
from __future__ import annotations

import os

# Directories
DIRECTORIES = [
    (1, "/src"),
    (2, "/src/parser"),
    (3, "/src/cli"),
]

# Files (id, path, dir_id)
FILES = [
    (1, "/src/parser/lexer.py", 2),
    (2, "/src/parser/parser.py", 2),
    (3, "/src/parser/ast.py", 2),
    (4, "/src/build.py", 1),
    (5, "/src/cli/main.py", 3),
    (6, "/src/util/log.py", 1),
]

# Definitions (id, name, file_id, kind)
DEFINITIONS = [
    (1, "tokenize", 1, "function"),     # epicenter target in the demo
    (2, "parse", 2, "function"),        # calls tokenize
    (3, "build_ast", 3, "function"),    # calls parse
    (4, "compile_unit", 4, "function"), # calls build_ast
    (5, "main", 5, "function"),         # calls compile_unit
    (6, "lint", 4, "function"),         # calls parse (second ring-1 path to parse)
    (7, "format_src", 4, "function"),   # calls build_ast
    (8, "log_event", 6, "function"),    # unrelated, no path to tokenize
    (9, "load_config", 5, "function"),  # unrelated
    (10, "Token", 1, "class"),          # tokenize uses it but nothing depends through it for the demo
]

# Edges (src_id, dst_id, type): src CALLS dst.
EDGES = [
    (2, 1, "calls"),   # parse -> tokenize
    (3, 2, "calls"),   # build_ast -> parse
    (4, 3, "calls"),   # compile_unit -> build_ast
    (5, 4, "calls"),   # main -> compile_unit
    (6, 2, "calls"),   # lint -> parse
    (7, 3, "calls"),   # format_src -> build_ast
    (5, 9, "calls"),   # main -> load_config (off the tokenize path)
    (2, 10, "imports"), # parse -> Token (import edge, not a call dependency)
]


def build_fixture_duckdb(path: str) -> str:
    """Create (overwrite) a DuckDB at `path` shaped like Orbit Local. Returns path."""
    import duckdb

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    con = duckdb.connect(path)
    try:
        con.execute("CREATE TABLE gl_directory (id INTEGER, path VARCHAR)")
        con.executemany("INSERT INTO gl_directory VALUES (?, ?)", DIRECTORIES)
        con.execute("CREATE TABLE gl_file (id INTEGER, path VARCHAR, dir_id INTEGER)")
        con.executemany("INSERT INTO gl_file VALUES (?, ?, ?)", FILES)
        con.execute("CREATE TABLE gl_definition (id INTEGER, name VARCHAR, file_id INTEGER, kind VARCHAR)")
        con.executemany("INSERT INTO gl_definition VALUES (?, ?, ?, ?)", DEFINITIONS)
        con.execute("CREATE TABLE gl_edge (src_id INTEGER, dst_id INTEGER, type VARCHAR)")
        con.executemany("INSERT INTO gl_edge VALUES (?, ?, ?)", EDGES)
        con.execute("CREATE TABLE _orbit_manifest (key VARCHAR, value VARCHAR)")
        con.executemany("INSERT INTO _orbit_manifest VALUES (?, ?)",
                        [("source", "keystone-fixture"), ("schema", "orbit-local-shaped")])
    finally:
        con.close()
    return path


# Seeded prior governance decisions for the Precedent Panel demo. The demo target
# is "tokenize". One PRIOR decision is a REJECTION on the same blast signature, so
# a pending approval on tokenize surfaces a real contradiction on camera.
def seed_ledger_rows():
    """Return the list of prior decision payloads to seed (oldest first).
    blast_radius_set is the set of affected definition ids for that decision."""
    return [
        {
            "actor": "h.okafor",
            "change_id": "MR-118",
            "target_symbols": ["parse"],
            "blast_radius_set": [3, 4, 5, 6, 7],
            "decision": "approve",
            "rationale": "Signature unchanged, added an optional kwarg with a default. Low risk.",
        },
        {
            "actor": "s.castellano",
            "change_id": "MR-203",
            "target_symbols": ["tokenize"],
            "blast_radius_set": [2, 3, 4, 5, 6, 7],
            "decision": "reject",
            "rationale": "Changes token boundary semantics; breaks parse and every downstream caller. Needs an RFC first.",
        },
    ]
