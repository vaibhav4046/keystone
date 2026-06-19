"""Lock the demo scenario's collision output to the deterministic engine.

The web simulator and the README quick-start both display specific numbers for
the MR-204 / MR-207 / MR-211 demo: collision kind ``blast_overlap``, fan-in
severity 6, five named shared dependents, and the Kahn safe merge order
``MR-204 -> MR-207 -> MR-211``. Those figures are produced by
``run_sample_harness`` over the committed Orbit self-index, then baked into
``web/data.json``. This test recomputes them from the engine so the displayed
numbers cannot silently drift from ``core/collision.py`` without failing CI.

Existing tests in test_harness.py only assert these fields are present and
non-empty; this one pins the exact values a judge sees, against the same
committed graph the static bundle is built from.
"""
import os

import pytest

import core.graph as graph_mod
from core.audit import Ledger
from harness.pipeline import run_sample_harness

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SELF_GRAPH = os.path.join(REPO, "data", "keystone_self_graph.duckdb")


@pytest.mark.skipif(not os.path.exists(SELF_GRAPH),
                    reason="committed Orbit self-index not present")
def test_demo_scenario_collision_matches_engine(tmp_path):
    os.environ["KEYSTONE_LEDGER_KEY"] = "keystone-public-sample-v1"
    import core.audit as _audit
    _audit._CACHED_KEY = None  # re-read the fixed sample key

    graph = graph_mod.Graph(path=SELF_GRAPH, mode="LIVE")
    try:
        ledger = Ledger(str(tmp_path / "ledger.jsonl"))
        report = run_sample_harness(graph, ledger)
    finally:
        graph.close()

    collision_report = report.collision_report

    # The Kahn topological safe merge order shown in the simulator and README.
    assert report.merge_order == ["MR-204", "MR-207", "MR-211"]

    # The headline collision: MR-204 vs MR-211 is a blast_overlap (their blast
    # radii share five dependents), severity 6. Engine output, not a literal.
    pair = next((c for c in collision_report["collisions"]
                 if {c["mr_a"], c["mr_b"]} == {"MR-204", "MR-211"}), None)
    assert pair is not None, "expected an MR-204 / MR-211 collision"
    assert pair["kind"] == "blast_overlap"
    assert pair["severity"] == 6
    assert set(pair["shared"]) == {
        "approve", "get_json", "main", "post_json", "precedent",
    }
