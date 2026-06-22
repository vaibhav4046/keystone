"""Build the committed external-repo Orbit graphs that pin the secondary hero numbers.

The hero panel cites three real cross-MR collisions. pallets/click (64) is pinned by a
committed Orbit index. This script freezes the other two so they ALSO reproduce on a
committed artifact instead of living only as numbers in a JSON cache:

  benjaminp/six  -> _resolve x __get_module, 3   (data/six_graph.duckdb)
  psf/requests   -> values x set_cookie, 48       (data/requests_graph.duckdb)

Each graph is built by the same deterministic `repo_scan` pass the product uses, so the
numbers are not asserted by hand - they recompute from the graph. Re-running fetches each
repo's CURRENT default branch over the network; if upstream changes shape the counts can
drift, so the COMMITTED .duckdb is the source of truth and tests/test_external_repo.py
pins find_top_collision against it. Regenerate only when intentionally refreshing.

Usage:  python scripts/build_external_graphs.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import repo_scan, collision  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# (repo spec, output filename, expected collision) - expected is a build-time sanity check only.
TARGETS = [
    ("benjaminp/six", "six_graph.duckdb", ("_resolve", "__get_module", 3)),
    ("psf/requests", "requests_graph.duckdb", ("values", "set_cookie", 48)),
]


def main() -> int:
    from core import graph as graph_mod
    for spec, fname, expected in TARGETS:
        owner, repo, branch = repo_scan.parse_repo_spec(spec)
        sources = repo_scan.fetch_github_python(owner, repo, branch)
        if not sources:
            print("FAILED %s: no sources fetched (private, empty, or rate-limited)" % spec)
            return 1
        out = os.path.join(DATA, fname)
        repo_scan.build_graph_duckdb(sources, out, "%s/%s" % (owner, repo))
        top = collision.find_top_collision(graph_mod.Graph(path=out, mode="LIVE"))
        got = (top["a"], top["b"], top["shared_count"]) if top else None
        ea, eb, ec = expected
        ok = top and {top["a"], top["b"]} == {ea, eb} and top["shared_count"] == ec
        print("%s -> %s  files=%d  %s" % (spec, got, len(sources), "OK" if ok else "DRIFT vs %s" % (expected,)))
        if not ok:
            print("  note: upstream may have changed; the committed graph + test remain the source of truth")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
