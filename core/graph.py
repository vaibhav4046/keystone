"""Pure-Python graph engine over the Orbit Local DuckDB (or committed fixture).

No web imports, no LLM. Opens the DuckDB read-only, INTROSPECTS the schema before
querying (master-prompt Invariant two: only gl_definition.name is documented, so
never hardcode a column blindly), and exposes deterministic reads. Every number
the product shows comes from here, computed from real rows, reproducible.

Source resolution and honest labeling (Invariant four):
  - LIVE   : a valid Orbit Local DuckDB at ~/.orbit/graph.duckdb
  - FALLBACK: the committed fixture, used when the live DuckDB is absent/invalid
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from . import fixtures

LIVE_DUCKDB = os.path.join(os.path.expanduser("~"), ".orbit", "graph.duckdb")
FIXTURE_DUCKDB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "fixture_graph.duckdb")
FIXTURE_DUCKDB = os.path.abspath(FIXTURE_DUCKDB)

EXPECTED_TABLES = {"gl_definition", "gl_file", "gl_directory", "gl_edge"}


@dataclass
class Source:
    mode: str          # "LIVE" or "FALLBACK"
    path: str
    tables: list
    valid: bool


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
            try:
                info = self._con.execute(f"PRAGMA table_info('{t}')").fetchall()
                self._cols[t] = [row[1] for row in info]  # row[1] = column name
            except Exception:
                self._cols[t] = []

    def schema_report(self) -> dict:
        return {"mode": self.source.mode, "path": self.source.path,
                "tables": self.source.tables, "columns": self._cols}

    def find_definition(self, name: str) -> Optional[dict]:
        rows = self._con.execute(
            "SELECT id, name, file_id, kind FROM gl_definition WHERE name = ?", [name]
        ).fetchall()
        if not rows:
            return None
        i, n, fid, kind = rows[0]
        return {"id": i, "name": n, "file_id": fid, "kind": kind}

    def all_definition_names(self) -> list:
        return [r[0] for r in self._con.execute(
            "SELECT name FROM gl_definition ORDER BY name").fetchall()]

    def direct_callers(self, def_id: int) -> list:
        """Definition ids that CALL def_id (reverse 'calls' edges)."""
        rows = self._con.execute(
            "SELECT src_id FROM gl_edge WHERE dst_id = ? AND type = 'calls'", [def_id]
        ).fetchall()
        return sorted({r[0] for r in rows})

    def owning_file_and_dir(self, def_id: int) -> dict:
        rows = self._con.execute(
            """SELECT d.name, f.path, dir.path
               FROM gl_definition d
               JOIN gl_file f ON d.file_id = f.id
               LEFT JOIN gl_directory dir ON f.dir_id = dir.id
               WHERE d.id = ?""", [def_id]
        ).fetchall()
        if not rows:
            return {}
        name, fpath, dpath = rows[0]
        return {"name": name, "file": fpath, "dir": dpath}

    def name_of(self, def_id: int) -> str:
        rows = self._con.execute("SELECT name FROM gl_definition WHERE id = ?", [def_id]).fetchall()
        return rows[0][0] if rows else str(def_id)

    def total_definitions(self) -> int:
        return self._con.execute("SELECT count(*) FROM gl_definition").fetchone()[0]

    def close(self):
        try:
            self._con.close()
        except Exception:
            pass
