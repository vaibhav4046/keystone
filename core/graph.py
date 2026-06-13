"""Pure-Python graph engine over the Orbit Local DuckDB (or committed fixture).

No web imports, no LLM. Opens the DuckDB read-only, INTROSPECTS the schema before
querying, and exposes deterministic reads. Every number the product shows comes
from here, computed from real rows, reproducible.

Schema (verified against `glab orbit local schema`, orbit binary v0.74.0):
  gl_definition(id, name, fqn, file_path, definition_type, start_line, end_line, ...)
  gl_edge(source_id, source_kind, relationship_kind, target_id, target_kind, ...)
  gl_file(id, path, name, extension, language, ...)
  gl_directory(id, path, name, ...)
A CALLS edge (source_kind='Definition' -> target_kind='Definition') means the
source definition calls the target. Reverse those edges to get dependents.

Source resolution and honest labeling:
  - LIVE    : a valid Orbit Local DuckDB at ~/.orbit/graph.duckdb
  - FALLBACK: the committed fixture, used when the live DuckDB is absent/invalid
"""
from __future__ import annotations

import os
import posixpath
from dataclasses import dataclass
from typing import Optional

from . import fixtures

LIVE_DUCKDB = os.path.join(os.path.expanduser("~"), ".orbit", "graph.duckdb")
FIXTURE_DUCKDB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "fixture_graph.duckdb")
FIXTURE_DUCKDB = os.path.abspath(FIXTURE_DUCKDB)

EXPECTED_TABLES = {"gl_definition", "gl_file", "gl_directory", "gl_edge"}

# definition_type values worth listing as reviewable symbols (real Orbit values).
CALLABLE_TYPES = ("Function", "Method", "DecoratedFunction", "Class", "DecoratedClass")


@dataclass
class Source:
    mode: str          # "LIVE" or "FALLBACK"
    path: str
    tables: list
    valid: bool


def _safe_ident(name: str) -> bool:
    """A table identifier safe to interpolate into a PRAGMA (letters, digits, _)."""
    return bool(name) and all(c.isalnum() or c == "_" for c in name)


def _ensure_fixture() -> str:
    if not os.path.exists(FIXTURE_DUCKDB):
        fixtures.build_fixture_duckdb(FIXTURE_DUCKDB)
    return FIXTURE_DUCKDB


def _is_valid_duckdb(path: str) -> bool:
    if not path or not os.path.exists(path):
        return False
    try:
        import duckdb
        con = duckdb.connect(path, read_only=True)
        try:
            names = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
            return EXPECTED_TABLES.issubset(names)
        finally:
            con.close()
    except Exception:
        return False


class Graph:
    """Read-only graph reader with live-vs-fallback resolution and introspection."""

    def __init__(self, prefer_live: bool = True):
        import duckdb
        self._duckdb = duckdb
        if prefer_live and _is_valid_duckdb(LIVE_DUCKDB):
            self.source = Source("LIVE", LIVE_DUCKDB, [], True)
        else:
            self.source = Source("FALLBACK", _ensure_fixture(), [], True)
        self._con = duckdb.connect(self.source.path, read_only=True)
        self._cols = {}
        self._introspect()

    def _introspect(self):
        names = [r[0] for r in self._con.execute("SHOW TABLES").fetchall()]
        self.source.tables = names
        for t in names:
            # defensive: only introspect well-formed identifiers (the DB is
            # Orbit-controlled, but never interpolate an unexpected name into SQL)
            if not _safe_ident(t):
                self._cols[t] = []
                continue
            try:
                info = self._con.execute(f"PRAGMA table_info('{t}')").fetchall()
                self._cols[t] = [row[1] for row in info]  # row[1] = column name
            except Exception:
                self._cols[t] = []

    def has(self, table: str, col: str) -> bool:
        return col in self._cols.get(table, [])

    def schema_report(self) -> dict:
        return {"mode": self.source.mode, "path": self.source.path,
                "tables": self.source.tables, "columns": self._cols}

    # --- core reads (real Orbit schema) ---

    def _fanin_subquery(self) -> str:
        return ("(SELECT COUNT(*) FROM gl_edge e WHERE e.target_id = d.id "
                "AND e.relationship_kind = 'CALLS' AND e.source_kind = 'Definition' "
                "AND e.target_kind = 'Definition')")

    def find_definition(self, name: str) -> Optional[dict]:
        """Resolve a name (or a fully-qualified name) to one definition.

        A qualified query (containing a dot, matching gl_definition.fqn) resolves
        exactly, so callers can disambiguate two same-short-name symbols. A bare
        short name resolves to the definition with the most callers (the most
        consequential to change), tie-break by id; the returned fqn + file let the
        UI show exactly which symbol was picked so it can never silently mislead."""
        col = "fqn" if ("." in name and self.has("gl_definition", "fqn")) else "name"
        rows = self._con.execute(
            f"SELECT d.id, d.name, d.fqn, d.file_path, d.definition_type, {self._fanin_subquery()} AS fanin "
            f"FROM gl_definition d WHERE d.{col} = ? ORDER BY fanin DESC, d.id ASC LIMIT 1",
            [name],
        ).fetchall()
        if not rows:
            return None
        i, n, fqn, fpath, dtype, _fan = rows[0]
        return {"id": i, "name": n, "fqn": fqn or "", "file": fpath or "", "kind": dtype}

    def all_definition_names(self, limit: int = 120) -> list:
        """Distinct reviewable symbol names (functions/methods/classes), ordered by
        caller fan-in then name, so the most consequential symbols surface first."""
        type_list = ",".join("'%s'" % t for t in CALLABLE_TYPES)
        rows = self._con.execute(
            f"SELECT d.name, MAX({self._fanin_subquery()}) AS fanin "
            f"FROM gl_definition d WHERE d.definition_type IN ({type_list}) "
            "AND d.name IS NOT NULL AND d.name <> '' "
            "GROUP BY d.name ORDER BY fanin DESC, d.name ASC LIMIT ?",
            [limit],
        ).fetchall()
        names = [r[0] for r in rows]
        if not names:  # extreme fallback: any named definition
            names = [r[0] for r in self._con.execute(
                "SELECT DISTINCT name FROM gl_definition WHERE name IS NOT NULL AND name <> '' "
                "ORDER BY name LIMIT ?", [limit]).fetchall()]
        return names

    def direct_callers(self, def_id: int) -> list:
        """Definition ids that CALL def_id (reverse CALLS edges, Definition->Definition)."""
        rows = self._con.execute(
            "SELECT source_id FROM gl_edge WHERE target_id = ? AND relationship_kind = 'CALLS' "
            "AND source_kind = 'Definition' AND target_kind = 'Definition'", [def_id]
        ).fetchall()
        # exclude self-edges defensively
        return sorted({r[0] for r in rows if r[0] != def_id})

    def owning_file_and_dir(self, def_id: int) -> dict:
        rows = self._con.execute(
            "SELECT name, file_path FROM gl_definition WHERE id = ?", [def_id]
        ).fetchall()
        if not rows:
            return {}
        name, fpath = rows[0]
        fpath = fpath or ""
        d = posixpath.dirname(fpath.replace("\\", "/")) if fpath else ""
        return {"name": name, "file": fpath, "dir": d}

    def name_of(self, def_id: int) -> str:
        rows = self._con.execute("SELECT name FROM gl_definition WHERE id = ?", [def_id]).fetchall()
        return rows[0][0] if rows else str(def_id)

    def total_definitions(self) -> int:
        return self._con.execute("SELECT count(*) FROM gl_definition").fetchone()[0]

    def repo_label(self) -> Optional[str]:
        """Best-effort repo name from the manifest, for the status panel."""
        if "_orbit_manifest" not in self._cols:
            return None
        try:
            row = self._con.execute("SELECT repo_path FROM _orbit_manifest LIMIT 1").fetchone()
            return row[0] if row else None
        except Exception:
            return None

    def close(self):
        try:
            self._con.close()
        except Exception:
            pass
