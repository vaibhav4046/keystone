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
    (5, "/src/io", "io"),
    (6, "/src/api", "api"),
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
    (8, "/src/io/serialize.py", "serialize.py", "py", "python"),
    (9, "/src/io/db.py", "db.py", "py", "python"),
    (10, "/src/io/cache.py", "cache.py", "py", "python"),
    (11, "/src/api/handlers.py", "handlers.py", "py", "python"),
    (12, "/src/api/routes.py", "routes.py", "py", "python"),
    (13, "/src/io/export.py", "export.py", "py", "python"),
    (14, "/src/util/metrics.py", "metrics.py", "py", "python"),
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
    # Second cluster: a serialization hot path with a high-fan-in hub, so exploring
    # the public FALLBACK graph beyond the scripted tokenize demo shows real depth.
    (11, "serialize", "io.serialize.serialize", "/src/io/serialize.py", "Function", 10, 60),    # hub: many dependents
    (12, "encode", "io.serialize.encode", "/src/io/serialize.py", "Function", 62, 90),
    (13, "to_json", "io.serialize.to_json", "/src/io/serialize.py", "Function", 92, 120),        # calls serialize
    (14, "to_yaml", "io.serialize.to_yaml", "/src/io/serialize.py", "Function", 122, 150),       # calls serialize
    (15, "save_doc", "io.db.save_doc", "/src/io/db.py", "Function", 8, 44),                       # calls to_json
    (16, "cache_put", "io.cache.cache_put", "/src/io/cache.py", "Function", 6, 30),               # calls serialize
    (17, "handle_get", "api.handlers.handle_get", "/src/api/handlers.py", "Function", 12, 50),    # calls to_json
    (18, "handle_post", "api.handlers.handle_post", "/src/api/handlers.py", "Function", 52, 96),  # calls save_doc
    (19, "route", "api.routes.route", "/src/api/routes.py", "Function", 10, 70),                  # calls handle_get/post
    (20, "render", "io.serialize.render", "/src/io/serialize.py", "Function", 152, 180),          # calls serialize
    (21, "export_csv", "io.export.export_csv", "/src/io/export.py", "Function", 6, 40),           # calls serialize
    (22, "validate", "io.serialize.validate", "/src/io/serialize.py", "Function", 182, 210),      # calls encode
    (23, "healthcheck", "api.routes.healthcheck", "/src/api/routes.py", "Function", 72, 90),      # calls route
    (24, "metrics", "util.metrics.metrics", "/src/util/metrics.py", "Function", 4, 30),           # standalone
    (25, "Logger", "util.log.Logger", "/src/util/log.py", "Class", 22, 60),                       # standalone
]

# gl_edge: (source_id, source_kind, relationship_kind, target_id, target_kind)
# CALLS edges (Definition -> Definition) drive the blast radius. source calls target.
_CALLS = [
    # parser hot path (the scripted tokenize/parse demo; do not change)
    (2, 1),   # parse -> tokenize
    (3, 2),   # build_ast -> parse
    (6, 2),   # lint -> parse
    (4, 3),   # compile_unit -> build_ast
    (7, 3),   # format_src -> build_ast
    (5, 4),   # main -> compile_unit
    (5, 9),   # main -> load_config (off the tokenize path)
    # serialization hot path: serialize(11) is the hub with many dependents
    (13, 11),  # to_json -> serialize
    (14, 11),  # to_yaml -> serialize
    (16, 11),  # cache_put -> serialize
    (20, 11),  # render -> serialize
    (21, 11),  # export_csv -> serialize
    (11, 12),  # serialize -> encode
    (22, 12),  # validate -> encode
    (15, 13),  # save_doc -> to_json
    (17, 13),  # handle_get -> to_json
    (18, 15),  # handle_post -> save_doc
    (19, 17),  # route -> handle_get
    (19, 18),  # route -> handle_post
    (23, 19),  # healthcheck -> route
]
# DEFINES edges (File -> Definition): which file defines each definition.
_DEF_FILE = {
    1: 1, 2: 2, 3: 3, 4: 4, 6: 4, 7: 4, 5: 5, 8: 6, 9: 7, 10: 1,
    11: 8, 12: 8, 13: 8, 14: 8, 20: 8, 22: 8, 15: 9, 16: 10,
    17: 11, 18: 11, 19: 12, 23: 12, 21: 13, 24: 14, 25: 6,
}
# CONTAINS edges (Directory -> File) and (Directory -> Directory) for fidelity.
_DIR_FILES = [(1, 4), (2, 1), (2, 2), (2, 3), (3, 5), (3, 7), (4, 6),
              (5, 8), (5, 9), (5, 10), (5, 13), (6, 11), (6, 12), (4, 14)]
_DIR_DIRS = [(1, 2), (1, 3), (1, 4), (1, 5), (1, 6)]


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
            "actor": "h.okafor", "change_id": "MR-118", "target_symbols": ["parse"], "epicenter_id": 2,
            "blast_radius_set": [3, 4, 5, 6, 7], "decision": "approve",
            "rationale": "Signature unchanged, added an optional kwarg with a default. Low risk.",
        },
        {
            "actor": "d.nguyen", "change_id": "MR-140", "target_symbols": ["build_ast"], "epicenter_id": 3,
            "blast_radius_set": [4, 5, 7], "decision": "approve",
            "rationale": "Adds an AST node type; existing nodes untouched, dependents unchanged.",
        },
        {
            "actor": "h.okafor", "change_id": "MR-152", "target_symbols": ["serialize"], "epicenter_id": 11,
            "blast_radius_set": [13, 14, 15, 16, 17, 18, 19, 20, 21], "decision": "approve",
            "rationale": "Pure-internal buffer reuse; output bytes identical, all nine dependents recompute the same.",
        },
        {
            "actor": "s.castellano", "change_id": "MR-161", "target_symbols": ["compile_unit"], "epicenter_id": 4,
            "blast_radius_set": [5], "decision": "reject",
            "rationale": "Changes the compile cache key; main would silently use stale artifacts. Needs a cache-bust first.",
        },
        {
            "actor": "a.silva", "change_id": "MR-177", "target_symbols": ["to_json"], "epicenter_id": 13,
            "blast_radius_set": [15, 17, 18, 19, 23], "decision": "approve",
            "rationale": "Field ordering only; consumers parse by key. Five dependents, no behavioural change.",
        },
        {
            "actor": "s.castellano", "change_id": "MR-203", "target_symbols": ["tokenize"], "epicenter_id": 1,
            # Same affected set the engine computes for tokenize at the default depth,
            # so the contradiction fires on a SIGNATURE-IDENTICAL prior rejection.
            "blast_radius_set": [2, 3, 4, 6, 7], "decision": "reject",
            "rationale": "Changes token boundary semantics; breaks parse and every downstream caller. Needs an RFC first.",
        },
        {
            "actor": "d.nguyen", "change_id": "MR-205", "target_symbols": ["handle_post"], "epicenter_id": 18,
            "blast_radius_set": [19, 23], "decision": "approve",
            "rationale": "Adds request validation; route and healthcheck unaffected. Low blast radius.",
        },
    ]
