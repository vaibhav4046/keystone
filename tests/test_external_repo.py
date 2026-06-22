"""Generality proof (priority G).

The SAME deterministic collision engine that runs on Keystone's own Orbit self-index also
finds genuine cross-MR collisions on pallets/click - a well-known third-party library Keystone
did not write - so the result is not tuned to our own code. Reproduce on the CLI with:

    python skills/keystone/run_review.py shadow-merge --graph data/click_graph.duckdb \
        --a Context --b echo            # real blast_overlap, 14 shared dependents -> HOLD
    python skills/keystone/run_review.py shadow-merge --graph data/click_graph.duckdb \
        --a echo --b make_context       # real change_in_blast -> BLOCK, exit 2
"""
import os

import pytest

from core import collision as collision_mod, graph as graph_mod, impact as impact_mod

CLICK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "click_graph.duckdb")


@pytest.mark.skipif(not os.path.exists(CLICK), reason="pallets/click graph not indexed")
def test_engine_finds_real_collision_on_external_repo():
    g = graph_mod.Graph(prefer_live=True, path=CLICK)
    a = impact_mod.compute_blast_radius(g, "Context")
    b = impact_mod.compute_blast_radius(g, "echo")
    assert a is not None and b is not None, "click symbols must resolve in the indexed graph"
    assert a.epicenter_file != b.epicenter_file, "the two changes must live in different files (no Git conflict)"
    res = collision_mod.detect_collisions(
        g, [{"id": "MR-1", "symbols": ["Context"]}, {"id": "MR-2", "symbols": ["echo"]}])
    cols = (res or {}).get("collisions") or []
    assert cols, "the engine must detect a genuine cross-MR collision on a third-party repo"
    assert cols[0]["kind"] in ("blast_overlap", "change_in_blast", "same_change")
    assert len(cols[0].get("shared", [])) >= 3, "the shared-dependent set must be non-trivial"


@pytest.mark.skipif(not os.path.exists(CLICK), reason="pallets/click graph not indexed")
def test_external_repo_blast_radius_is_real_and_large():
    g = graph_mod.Graph(prefer_live=True, path=CLICK)
    ctx = impact_mod.compute_blast_radius(g, "Context")
    assert ctx is not None
    # Context is a hub in click; its real dependent count is large (not a tuned demo number).
    assert ctx.counts.get("total_affected", 0) >= 50


SIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "six_graph.duckdb")
REQUESTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "requests_graph.duckdb")


def test_six_secondary_hero_number_reproduces():
    # Every cited collision number must reproduce on a committed artifact, not just live in a cache.
    assert os.path.exists(SIX), "committed data/six_graph.duckdb missing (scripts/build_external_graphs.py)"
    top = collision_mod.find_top_collision(graph_mod.Graph(prefer_live=True, path=SIX))
    assert top is not None
    assert {top["a"], top["b"]} == {"_resolve", "__get_module"}
    assert top["shared_count"] == 3


def test_requests_secondary_hero_number_reproduces():
    assert os.path.exists(REQUESTS), "committed data/requests_graph.duckdb missing (scripts/build_external_graphs.py)"
    top = collision_mod.find_top_collision(graph_mod.Graph(prefer_live=True, path=REQUESTS))
    assert top is not None
    assert {top["a"], top["b"]} == {"values", "set_cookie"}
    assert top["shared_count"] == 48


AXIOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "axios_graph.duckdb")
CHALK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "chalk_graph.duckdb")


def test_axios_javascript_collision_reproduces():
    # the SAME engine finds a genuine cross-MR collision on a real, multi-file JavaScript library
    # (axios), committed + pinned exactly like the Python repos - multi-language proven end-to-end.
    assert os.path.exists(AXIOS), "committed data/axios_graph.duckdb missing (scripts/build_external_graphs.py)"
    top = collision_mod.find_top_collision(graph_mod.Graph(prefer_live=True, path=AXIOS))
    assert top is not None
    assert {top["a"], top["b"]} == {"isBuffer", "isObject"}
    assert top["shared_count"] == 62
    # the shared dependents are real axios functions (not Array builtins like push/forEach)
    assert all(name.isidentifier() for name in top["shared"]) and "push" not in top["shared"]


def test_chalk_javascript_collision_reproduces():
    assert os.path.exists(CHALK), "committed data/chalk_graph.duckdb missing (scripts/build_external_graphs.py)"
    top = collision_mod.find_top_collision(graph_mod.Graph(prefer_live=True, path=CHALK))
    assert top is not None
    assert {top["a"], top["b"]} == {"stringEncaseCRLFWithFirstIndex", "stringReplaceAll"}
    assert top["shared_count"] == 4


def test_click_headline_pair_is_stable_in_default_window():
    # The headline is honestly "the worst among the top-K most-consequential symbols", so it must
    # be STABLE across the default window and never silently shift. A larger top_k can surface a
    # bigger collision among less-central symbols (top_k=60 -> 71) - that is expected + documented,
    # not the pinned headline.
    g = graph_mod.Graph(prefer_live=True, path=CLICK)
    for k in (25, 30, 40):
        top = collision_mod.find_top_collision(g, top_k=k)
        assert {top["a"], top["b"]} == {"Parameter", "HelpFormatter"}, "headline pair shifted at top_k=%d" % k
        assert top["shared_count"] == 64
