"""Build data/orbit_remote_fixture.duckdb - a committed, SYNTHETIC Orbit Remote SDLC graph.

Keystone has no paid GitLab Ultimate + Orbit Remote instance, so this generates a fixture in the
REAL Orbit Remote schema (gl_codeowners, gl_commit_recency, gl_pipeline_history, gl_security_finding)
with DETERMINISTIC synthetic data keyed to this repo's own files (from data/keystone_self_graph.duckdb).
The data is synthetic and labelled so (core/enrich.py sets source=ORBIT_REMOTE_FIXTURE, synthetic=true);
the schema and the gate logic that runs over it are real. Deterministic (no clock, no randomness):
all values are a stable function of the file path, so the committed fixture rebuilds byte-stably.

Usage:  python scripts/build_orbit_remote_fixture.py
"""
from __future__ import annotations

import hashlib
import os
import posixpath
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
SELF = os.path.join(DATA, "keystone_self_graph.duckdb")
OUT = os.path.join(DATA, "orbit_remote_fixture.duckdb")


def _h(s: str) -> int:
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest()[:8], 16)


def main() -> int:
    import duckdb
    src = duckdb.connect(SELF, read_only=True)
    files = sorted({r[0] for r in src.execute("SELECT DISTINCT file_path FROM gl_definition").fetchall() if r[0]})
    names = sorted({r[0] for r in src.execute("SELECT DISTINCT name FROM gl_definition").fetchall() if r[0]})
    src.close()
    if os.path.exists(OUT):
        os.remove(OUT)
    con = duckdb.connect(OUT)
    con.execute("CREATE TABLE gl_codeowners (path VARCHAR, owners VARCHAR)")
    con.execute("CREATE TABLE gl_commit_recency (file_path VARCHAR, last_commit_at VARCHAR, distinct_authors BIGINT)")
    con.execute("CREATE TABLE gl_pipeline_history (file_path VARCHAR, runs BIGINT, failures BIGINT, last_failure_at VARCHAR)")
    con.execute("CREATE TABLE gl_security_finding (definition_name VARCHAR, severity VARCHAR, advisory VARCHAR)")

    # OWNERS by directory, deterministically; a few files are intentionally unowned/stale to
    # demonstrate the ownership-entropy gate firing.
    team = ["@core-team", "@backend-team", "@platform", "@security", "@web", "@release"]
    co, rec, pipe = [], [], []
    for f in files:
        d = posixpath.dirname(f) or "."
        owner = team[_h(d) % len(team)]
        second = team[_h(f) % len(team)]
        owners = owner if owner == second else owner + "," + second
        unowned = (_h(f) % 11 == 0)            # ~9% of files have no CODEOWNERS entry
        if not unowned:
            co.append((f, owners))
        stale = (_h("rec" + f) % 7 == 0)
        last = "2025-06-%02dT00:00:00Z" % (1 + _h(f) % 28) if stale else "2026-05-%02dT00:00:00Z" % (1 + _h(f) % 28)
        rec.append((f, last, 1 + _h("auth" + f) % 5))
        runs = 40 + _h("runs" + f) % 60
        fails = (runs * (25 + _h("fail" + f) % 40)) // 100 if (_h("flaky" + f) % 6 == 0) else _h("f" + f) % 3
        pipe.append((f, runs, fails, last))
    con.executemany("INSERT INTO gl_codeowners VALUES (?, ?)", co)
    con.executemany("INSERT INTO gl_commit_recency VALUES (?, ?, ?)", rec)
    con.executemany("INSERT INTO gl_pipeline_history VALUES (?, ?, ?, ?)", pipe)

    sevs = ["high", "medium", "high", "critical"]
    sec = []
    for nm in names:
        if _h("sec" + nm) % 53 == 0:           # a sparse, deterministic subset of symbols
            sec.append((nm, sevs[_h(nm) % len(sevs)], "GHSA-synthetic-%04x (fixture)" % (_h(nm) % 0xffff)))
    con.executemany("INSERT INTO gl_security_finding VALUES (?, ?, ?)", sec)
    con.close()
    print("wrote %s: %d files, %d owned, %d pipeline rows, %d security findings"
          % (OUT, len(files), len(co), len(pipe), len(sec)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
