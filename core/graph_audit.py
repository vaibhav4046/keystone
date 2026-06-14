"""Graph-audit hazards: risk the Orbit call graph knows that the review surface hides.

The second hazard in Keystone's 'X-ray the graph' thesis (the first is cross-MR blast
collisions, core/collision.py). REVIEW DEBT: a symbol with a large blast radius that NO
test file directly exercises is a change that is simultaneously high-impact and unverified
- the worst kind to approve blind. Git, the MR diff, and CODEOWNERS do not surface this;
the call graph does. Every figure is a deterministic graph read (core/graph.review_debt).

Honesty boundary: 'untested' means strictly 'no test file directly calls this symbol in the
Orbit call graph' - not a claim about transitive reachability or runtime coverage. The
report says so, and the engine never invents a number.
"""
from __future__ import annotations

from typing import Optional


def review_debt_report(graph, limit: int = 14) -> dict:
    """Rank high-blast, directly-untested symbols. Returns the hazard list + an honest
    method note + a one-line verdict for the panel."""
    items = graph.review_debt(limit=limit)
    untested = [r for r in items if r["untested"]]
    max_blast = max((r["blast"] for r in untested), default=0)
    verdict = (
        f"{len(untested)} high-consequence symbol(s) (up to {max_blast} dependents) have NO test "
        f"file directly exercising them - each is a change that is both high-impact and unverified."
    ) if untested else (f"{len(items)} symbols audited; none high-blast and untested." if items
                        else "No callable symbols to audit.")
    return {
        "hazard": "review_debt",
        "title": "High-blast symbols with no direct test coverage",
        "method": ("ranked by distinct direct callers (blast); 'untested' = no caller lives in a "
                   "test file in the Orbit call graph (direct callers only, not transitive)."),
        "items": items,
        "counts": {"flagged": len(items), "untested_high_blast": len(untested)},
        "verdict": verdict,
    }
