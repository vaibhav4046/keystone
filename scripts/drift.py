"""CLI: compute blast-radius drift between two Orbit graph snapshots.

Usage:
    python scripts/drift.py <prior.duckdb> <current.duckdb> [--depth N] [--top N]

Honest: reads both DuckDBs, never mutates. A symbol with blast 3 in the prior and 30 in the
current is a "silently rising risk" - a reviewer re-reading an older approval deserves to see
it. Standard library + duckdb; no LLM, no network.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from core.drift import compute_drift                    # noqa: E402


def _print(r: dict, top: int) -> None:
    if not r.get("ok"):
        print(json.dumps(r, indent=2))
        sys.exit(1)
    print(f"prior   : {r['prior_path']}   ({r['prior_count']} definitions)")
    print(f"current : {r['current_path']}   ({r['current_count']} definitions)")
    print(f"depth   : {r['max_depth']}")
    print(f"added   : {r['added_count']}    removed: {r['removed_count']}    "
          f"grew: {r['grew_count']}    shrunk: {r['shrunk_count']}    same: {r['same_count']}")
    print(f"signatures changed: {r['signatures_changed']}")
    if r["added"]:
        print("\nADDED (in current, not in prior):")
        for s in r["added"][:top]:
            print(f"  + {s}")
    if r["removed"]:
        print("\nREMOVED (in prior, not in current):")
        for s in r["removed"][:top]:
            print(f"  - {s}")
    if r["grew"]:
        print("\nGREW (blast radius went UP - review older approvals):")
        for s in r["grew"][:top]:
            print(f"  ! {s['symbol']:<30}  {s['prior_blast']:>3} -> {s['current_blast']:<3}  "
                  f"delta {s['delta']:+d}")
    if r["shrunk"]:
        print("\nSHRUNK (blast radius went DOWN):")
        for s in r["shrunk"][:top]:
            print(f"  v {s['symbol']:<30}  {s['prior_blast']:>3} -> {s['current_blast']:<3}  "
                  f"delta {s['delta']:+d}")


def main():
    p = argparse.ArgumentParser(description="Keystone blast-radius drift (two graphs)")
    p.add_argument("prior", help="path to the prior (baseline) Orbit DuckDB snapshot")
    p.add_argument("current", help="path to the current Orbit DuckDB snapshot")
    p.add_argument("--depth", type=int, default=3, help="BFS depth, same as live impact (1-8)")
    p.add_argument("--top", type=int, default=20, help="max rows per section (1-200)")
    p.add_argument("--json", action="store_true", help="emit the full JSON result, not a summary")
    args = p.parse_args()
    r = compute_drift(prior_path=args.prior, current_path=args.current,
                      max_depth=args.depth, top=args.top)
    if args.json:
        print(json.dumps(r, indent=2, default=str))
    else:
        _print(r, args.top)


if __name__ == "__main__":
    main()
