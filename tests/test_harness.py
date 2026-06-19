"""Tests for the Keystone Engineering Harness.

Covers: models, pipeline (sample mode), report generation, and
integration with the existing core/ modules. Every test runs
against the committed fixture for determinism.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest

# Ensure repo root is importable
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from harness.models import (
    HarnessTask, HarnessGateResult, HarnessReport, HarnessMode, AgentKind,
)
from harness.pipeline import run_harness, run_sample_harness, SAMPLE_MRS
from harness import report as report_mod
from core import graph as graph_mod, impact as impact_mod, seed as seed_mod
from core.audit import Ledger


# ---------- Fixtures ----------

@pytest.fixture
def graph():
    """A graph instance (fixture or self-index, whichever is available)."""
    self_graph = os.path.join(ROOT, "data", "keystone_self_graph.duckdb")
    if os.path.exists(self_graph):
        return graph_mod.Graph(path=self_graph)
    return graph_mod.Graph(prefer_live=False)


@pytest.fixture
def ledger():
    """A fresh seeded ledger in a temp directory."""
    path = os.path.join(tempfile.mkdtemp(), "test_harness_ledger.jsonl")
    led = Ledger(path)
    g = graph_mod.Graph(prefer_live=False)
    for row in seed_mod.seed_rows_for(g):
        sig = impact_mod.blast_radius_signature(
            row["blast_radius_set"], row.get("epicenter_id"))
        led.append(
            actor=row["actor"], change_id=row["change_id"],
            target_symbols=row["target_symbols"],
            blast_radius_set=row["blast_radius_set"], signature=sig,
            decision=row["decision"], rationale=row["rationale"])
    return led


# ---------- Model Tests ----------

class TestModels:

    def test_harness_task_defaults(self):
        t = HarnessTask()
        assert t.agent_kind == AgentKind.BOT
        assert isinstance(t.task_id, str)
        assert len(t.task_id) == 12

    def test_harness_task_to_dict(self):
        t = HarnessTask(agent_id="test-agent", symbols_touched=["foo"])
        d = t.to_dict()
        assert d["agent_id"] == "test-agent"
        assert d["symbols_touched"] == ["foo"]
        assert d["agent_kind"] == "bot"

    def test_gate_result_defaults(self):
        gr = HarnessGateResult(symbol="bar")
        assert gr.verdict == "ALLOW"
        assert gr.found is True

    def test_report_verdict_properties(self):
        r = HarnessReport()
        r.gate_results = [
            HarnessGateResult(symbol="a", verdict="ALLOW"),
            HarnessGateResult(symbol="b", verdict="BLOCK"),
            HarnessGateResult(symbol="c", verdict="HOLD"),
        ]
        assert r.blocked_symbols == ["b"]
        assert r.held_symbols == ["c"]
        assert r.allowed_symbols == ["a"]

    def test_harness_mode_values(self):
        assert HarnessMode.SAMPLE.value == "sample"
        assert HarnessMode.LOCAL.value == "local"
        assert HarnessMode.GITLAB_MR.value == "gitlab_mr"


# ---------- Pipeline Tests ----------

class TestPipeline:

    def test_sample_harness_runs(self, graph, ledger):
        result = run_sample_harness(graph, ledger)
        assert isinstance(result, HarnessReport)
        assert result.mode == HarnessMode.SAMPLE
        assert result.task is not None
        assert result.task.agent_id == "copilot-workspace"

    def test_sample_harness_has_gate_results(self, graph, ledger):
        result = run_sample_harness(graph, ledger)
        assert len(result.gate_results) >= 1
        # The primary MR touches compute_blast_radius
        symbols = [g.symbol for g in result.gate_results]
        assert "compute_blast_radius" in symbols

    def test_sample_harness_has_pipeline_stages(self, graph, ledger):
        result = run_sample_harness(graph, ledger)
        stage_names = [s["name"] for s in result.pipeline_stages]
        assert "SYMBOL_RESOLVE" in stage_names
        assert "BLAST_COMPUTE" in stage_names
        assert "POLICY_GATE" in stage_names
        assert "COLLISION_SCAN" in stage_names
        assert "VERDICT" in stage_names

    def test_sample_harness_collision_detection(self, graph, ledger):
        result = run_sample_harness(graph, ledger)
        # With 3 MRs, collision detection should produce results
        assert result.collision_report is not None
        assert "collisions" in result.collision_report.get("counts", {})

    def test_sample_harness_has_merge_order(self, graph, ledger):
        result = run_sample_harness(graph, ledger)
        assert result.merge_order is not None
        assert isinstance(result.merge_order, list)

    def test_overall_verdict_is_worst(self, graph, ledger):
        result = run_sample_harness(graph, ledger)
        verdicts = [g.verdict for g in result.gate_results]
        if "BLOCK" in verdicts:
            assert result.overall_verdict == "BLOCK"
        elif "HOLD" in verdicts:
            assert result.overall_verdict in ("HOLD", "BLOCK")

    def test_single_symbol_task(self, graph, ledger):
        task = HarnessTask(
            agent_id="test",
            symbols_touched=["append"],
            mr_id="TEST-1",
        )
        result = run_harness(task, graph, ledger, mode=HarnessMode.LOCAL)
        assert len(result.gate_results) == 1
        assert result.gate_results[0].symbol == "append"
        assert result.gate_results[0].found is True

    def test_missing_symbol_gets_blocked(self, graph, ledger):
        task = HarnessTask(
            agent_id="test",
            symbols_touched=["nonexistent_symbol_xyz"],
        )
        result = run_harness(task, graph, ledger, mode=HarnessMode.LOCAL)
        assert len(result.gate_results) == 1
        assert result.gate_results[0].found is False
        assert result.gate_results[0].verdict == "BLOCK"

    def test_dry_run_does_not_modify_ledger(self, graph, ledger):
        rows_before = len(ledger.rows())
        task = HarnessTask(symbols_touched=["append"])
        run_harness(task, graph, ledger, dry_run=True)
        assert len(ledger.rows()) == rows_before

    def test_orbit_snapshot_sha256(self, graph, ledger):
        result = run_sample_harness(graph, ledger)
        assert result.orbit_snapshot_sha256 is not None
        assert len(result.orbit_snapshot_sha256) == 64


# ---------- Report Tests ----------

class TestReport:

    def test_json_output(self, graph, ledger):
        result = run_sample_harness(graph, ledger)
        j = report_mod.to_json(result)
        parsed = json.loads(j)
        assert parsed["mode"] == "sample"
        assert "gate_results" in parsed
        assert "pipeline_stages" in parsed

    def test_markdown_output(self, graph, ledger):
        result = run_sample_harness(graph, ledger)
        md = report_mod.to_markdown(result)
        assert "# Keystone Engineering Harness Report" in md
        assert "Pipeline Stages" in md
        assert "Per-Symbol Verdicts" in md

    def test_mr_comment_output(self, graph, ledger):
        result = run_sample_harness(graph, ledger)
        comment = report_mod.to_mr_comment(result)
        assert "## Keystone Harness:" in comment
        assert "Symbol" in comment
        assert "Verdict" in comment

    def test_write_artifacts(self, graph, ledger):
        result = run_sample_harness(graph, ledger)
        out_dir = tempfile.mkdtemp()
        written = report_mod.write_artifacts(result, out_dir)
        assert "json" in written
        assert "markdown" in written
        assert "mr_comment" in written
        for path in written.values():
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0

    def test_json_round_trip(self, graph, ledger):
        result = run_sample_harness(graph, ledger)
        j = report_mod.to_json(result)
        parsed = json.loads(j)
        # Verify key structure survives round-trip
        assert parsed["task"]["agent_kind"] == "bot"
        assert isinstance(parsed["gate_results"], list)
        assert isinstance(parsed["pipeline_stages"], list)
