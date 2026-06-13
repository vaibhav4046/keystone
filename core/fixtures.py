"""Committed deterministic fixture graph and seeded audit ledger.

Keystone's live engine reads a real GitLab Orbit Local DuckDB. When that file is
absent or invalid (for example on a cold checkout, or a public static deploy),
the engine falls back to THIS committed fixture so the whole product, its tests,
and a cold-clicked deploy still work.

The fixture is built to the EXACT real Orbit Local schema (verified against
`glab orbit local schema`, orbit binary v0.74.0): gl_directory, gl_file,
gl_definition, gl_edge, gl_imported_symbol, _orbit_manifest, with the real column
names (gl_definition.file_path / definition_type / fqn; gl_edge.source_id /
target_id / relationship_kind / source_kind / target_kind). So the SAME engine
queries run unchanged against the fixture and against a real indexed graph.

Edge semantics match real Orbit: a CALLS edge (source -> target) means the source
definition calls the target, so the blast radius of changing a target T is
everything that DEPENDS ON T, found by walking CALLS edges in REVERSE from T
(callers, then callers of callers). Nothing here is random; ids and rows are fixed.

The fixture models a small parser hot path so blast-radius counts are knowable
and asserted in tests. Standard library plus duckdb only. No web imports, no LLM.
"""
from __future__ import annotations

import os

# gl_directory: (id, path, name)
DIRECTORIES = [
    (1, "/src", "src"),
    (2, "/src/parser", "parser"),
    (3, "/src/cli", "cli"),
    (4, "/src/util", "util"),
]

# gl_file: (id, path, name, extension, language)
FILES = [
    (1, "/src/parser/lexer.py", "lexer.py", "py", "python"),
    (2, "/src/parser/parser.py", "parser.py", "py", "python"),
    (3, "/src/parser/ast.py", "ast.py", "py", "python"),
    (4, "/src/build.py", "build.py", "py", "python"),
    (5, "/src/cli/main.py", "main.py", "py", "python"),
    (6, "/src/util/log.py", "log.py", "py", "python"),
    (7, "/src/cli/config.py", "config.py", "py", "python"),
]

# gl_definition: (id, name, fqn, file_path, definition_type, start_line, end_line)
DEFINITIONS = [
    (1, "tokenize", "parser.lexer.tokenize", "/src/parser/lexer.py", "Function", 12, 48),    # epicenter in the demo
    (2, "parse", "parser.parser.parse", "/src/parser/parser.py", "Function", 20, 96),         # calls tokenize
    (3, "build_ast", "parser.ast.build_ast", "/src/parser/ast.py", "Function", 8, 70),        # calls parse
    (4, "compile_unit", "build.compile_unit", "/src/build.py", "Function", 30, 88),           # calls build_ast
    (5, "main", "cli.main.main", "/src/cli/main.py", "Function", 10, 64),                      # calls compile_unit, load_config
    (6, "lint", "build.lint", "/src/build.py", "Function", 90, 140),                           # calls parse (2nd path to parse)
    (7, "format_src", "build.format_src", "/src/build.py", "Function", 142, 180),              # calls build_ast
    (8, "log_event", "util.log.log_event", "/src/util/log.py", "Function", 4, 20),             # unrelated, no path to tokenize
    (9, "load_config", "cli.config.load_config", "/src/cli/config.py", "Function", 6, 40),     # unrelated to tokenize
    (10, "Token", "parser.lexer.Token", "/src/parser/lexer.py", "Class", 50, 80),              # used by tokenize, no dependents in demo
]

# gl_edge: (source_id, source_kind, relationship_kind, target_id, target_kind)
# CALLS edges (Definition -> Definition) drive the blast radius. source calls target.
_CALLS = [
    (2, 1),   # parse -> tokenize
    (3, 2),   # build_ast -> parse
    (6, 2),   # lint -> parse
    (4, 3),   # compile_unit -> build_ast
    (7, 3),   # format_src -> build_ast
    (5, 4),   # main -> compile_unit
    (5, 9),   # main -> load_config (off the tokenize path)
]
# DEFINES edges (File -> Definition): which file defines each definition.
_DEF_FILE = {1: 1, 2: 2, 3: 3, 4: 4, 6: 4, 7: 4, 5: 5, 8: 6, 9: 7, 10: 1}
# CONTAINS edges (Directory -> File) and (Directory -> Directory) for fidelity.
_DIR_FILES = [(1, 4), (2, 1), (2, 2), (2, 3), (3, 5), (3, 7), (4, 6)]
_DIR_DIRS = [(1, 2), (1, 3), (1, 4)]


def _edges():
    rows = []
    for s, t in _CALLS:
        rows.append((s, "Definition", "CALLS", t, "Definition"))
    for def_id, file_id in _DEF_FILE.items():
        rows.append((file_id, "File", "DEFINES", def_id, "Definition"))
    for dir_id, file_id in _DIR_FILES:
        rows.append((dir_id, "Directory", "CONTAINS", file_id, "File"))
    for parent, child in _DIR_DIRS:
        rows.append((parent, "Directory", "CONTAINS", child, "Directory"))
    return rows


def build_fixture_duckdb(path: str) -> str:
    """Create (overwrite) a DuckDB at `path` shaped exactly like Orbit Local. Returns path."""
    import duckdb

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    con = duckdb.connect(path)
    try:
        con.execute("CREATE TABLE gl_directory (id BIGINT, path VARCHAR, name VARCHAR)")
        con.executemany("INSERT INTO gl_directory VALUES (?, ?, ?)", DIRECTORIES)

        con.execute("CREATE TABLE gl_file (id BIGINT, path VARCHAR, name VARCHAR, extension VARCHAR, language VARCHAR)")
        con.executemany("INSERT INTO gl_file VALUES (?, ?, ?, ?, ?)", FILES)

        con.execute("CREATE TABLE gl_definition (id BIGINT, name VARCHAR, fqn VARCHAR, file_path VARCHAR, "
                    "definition_type VARCHAR, start_line BIGINT, end_line BIGINT)")
        con.executemany("INSERT INTO gl_definition VALUES (?, ?, ?, ?, ?, ?, ?)", DEFINITIONS)

        con.execute("CREATE TABLE gl_edge (source_id BIGINT, source_kind VARCHAR, relationship_kind VARCHAR, "
                    "target_id BIGINT, target_kind VARCHAR)")
        con.executemany("INSERT INTO gl_edge VALUES (?, ?, ?, ?, ?)", _edges())

        # Present in real graphs; not required by the engine but kept for schema fidelity.
        con.execute("CREATE TABLE gl_imported_symbol (id BIGINT, file_path VARCHAR, import_type VARCHAR, "
                    "import_path VARCHAR, identifier_name VARCHAR)")
        con.executemany("INSERT INTO gl_imported_symbol VALUES (?, ?, ?, ?, ?)", [
            (1, "/src/parser/parser.py", "from", "parser.lexer", "tokenize"),
            (2, "/src/build.py", "from", "parser.parser", "parse"),
        ])

        con.execute("CREATE TABLE _orbit_manifest (repo_path VARCHAR, project_id BIGINT, parent_repo_path VARCHAR, "
                    "branch VARCHAR, commit_sha VARCHAR, status VARCHAR, last_indexed_at TIMESTAMP, error_message VARCHAR)")
        con.execute("INSERT INTO _orbit_manifest VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    ["keystone-fixture", None, None, "main", "fixture", "indexed", None, None])
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
            # Same affected set the engine computes for tokenize at the default depth,
            # so the contradiction fires on a SIGNATURE-IDENTICAL prior rejection,
            # the strongest form of the precedent beat.
            "blast_radius_set": [2, 3, 4, 6, 7],
            "decision": "reject",
            "rationale": "Changes token boundary semantics; breaks parse and every downstream caller. Needs an RFC first.",
        },
    ]
