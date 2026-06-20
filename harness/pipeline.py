"""Harness pipeline: the deterministic governance orchestrator.

This is the core of the Engineering Harness. It takes a HarnessTask (what an
agent changed), walks it through the Orbit code graph, and produces a
HarnessReport with per-symbol verdicts and cross-MR collision analysis.

Every computation delegates to existing core/ modules. The pipeline adds
ZERO new math or heuristics. It is pure orchestration and structured output.

Pipeline stages:
  1. SYMBOL_RESOLVE  - Validate each touched symbol exists in the graph
  2. BLAST_COMPUTE   - Compute blast radius for each symbol
  3. POLICY_GATE     - Evaluate the policy gate for each symbol
  4. COLLISION_SCAN  - Detect cross-MR blast collisions
  5. VERDICT         - Compute overall verdict and safe merge order
"""
from __future__ import annotations

import time
from typing import Optional

from .models import (
    HarnessTask, HarnessGateResult, HarnessReport, HarnessMode, AgentKind,
)

# Import paths are relative to the repo root (keystone/)
import sys
import os
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import (
    impact as impact_mod,
    policy as policy_mod,
    collision as collision_mod,
    attest as attest_mod,
)
from core.audit import Ledger

# The demo scenario: same MRs used by the simulator and run_review.py
SAMPLE_MRS = [
    {"id": "MR-204", "symbols": ["compute_blast_radius"],
     "title": "speed up the blast engine", "file": "core/impact.py",
     "agent": "copilot-workspace", "kind": "bot"},
    {"id": "MR-207", "symbols": ["impact"],
     "title": "tune the impact API", "file": "backend/app.py",
     "agent": "human-dev", "kind": "human"},
    {"id": "MR-211", "symbols": ["append"],
     "title": "ledger append fix", "file": "core/audit.py",
     "agent": "devin-agent", "kind": "bot"},
]

# Verdict priority (worst wins)
_VERDICT_RANK = {"ALLOW": 0, "HOLD": 1, "BLOCK": 2}


def _stage(name: str, status: str, detail: Optional[dict] = None,
           duration_ms: Optional[int] = None) -> dict:
    """Build a pipeline stage record."""
    s = {"name": name, "status": status}
    if detail:
        s["detail"] = detail
    if duration_ms is not None:
        s["duration_ms"] = duration_ms
    return s


def _resolve_symbols(graph, symbols: list) -> list:
    """Check which symbols exist in the graph. Returns list of (name, found)."""
    results = []
    for sym in symbols:
        imp = impact_mod.compute_blast_radius(graph, sym, max_depth=1)
        results.append((sym, imp is not None))
    return results


def run_harness(task: HarnessTask, graph, ledger: Ledger, *,
                mode: HarnessMode = HarnessMode.SAMPLE,
                open_mrs: Optional[list] = None,
                dry_run: bool = True) -> HarnessReport:
    """Execute the full harness pipeline for a single task.

    Args:
        task: The agent task to evaluate.
        graph: A core.graph.Graph instance.
        ledger: A core.audit.Ledger instance.
        mode: Execution mode (SAMPLE, LOCAL, GITLAB_MR).
        open_mrs: Other open MRs for collision detection.
                  Each: {"id": str, "symbols": [str]}
        dry_run: If True, do not append to the ledger.

    Returns:
        A HarnessReport with per-symbol verdicts and collision analysis.
    """
    report = HarnessReport(task=task, mode=mode)
    stages = []

    # --- Stage 1: Symbol Resolution ---
    t0 = time.time()
    resolved = _resolve_symbols(graph, task.symbols_touched)
    found_count = sum(1 for _, found in resolved if found)
    stages.append(_stage("SYMBOL_RESOLVE", "done",
                         {"total": len(resolved), "found": found_count,
                          "missing": [s for s, f in resolved if not f]},
                         int((time.time() - t0) * 1000)))

    # --- Stage 2: Blast Radius Computation ---
    t0 = time.time()
    gate_results = []
    for sym, found in resolved:
        gr = HarnessGateResult(symbol=sym, found=found)
        if not found:
            gr.verdict = "BLOCK"
            gr.reasons = [f"Symbol '{sym}' not found in the Orbit graph"]
            gate_results.append(gr)
            continue

        imp = impact_mod.compute_blast_radius(graph, sym, max_depth=3)
        if imp is None:
            gr.found = False
            gr.verdict = "BLOCK"
            gr.reasons = [f"Blast radius computation failed for '{sym}'"]
            gate_results.append(gr)
            continue

        gr.impact = imp.to_dict()

        # Precedent lookup
        fqns = [imp.epicenter_fqn] if imp.epicenter_fqn else None
        prec = ledger.precedent(target_symbols=[sym], signature=imp.signature,
                                target_fqns=fqns)
        gr.precedent = prec

        # Policy evaluation
        pol = policy_mod.evaluate(gr.impact, prec)
        gr.policy = pol
        gr.verdict = pol.get("action", "ALLOW")
        gr.reasons = pol.get("reasons", [])

        # Add agent-kind escalation: bot-authored changes on HOLD+ get a reason
        if task.agent_kind == AgentKind.BOT and gr.verdict != "ALLOW":
            gr.reasons.append(
                f"Agent-authored change (agent={task.agent_id}) on "
                f"{gr.verdict} tier requires human reviewer confirmation"
            )

        gate_results.append(gr)

    report.gate_results = gate_results
    stages.append(_stage("BLAST_COMPUTE", "done",
                         {"symbols_evaluated": len(gate_results)},
                         int((time.time() - t0) * 1000)))

    # --- Stage 3: Policy Gate ---
    t0 = time.time()
    stages.append(_stage("POLICY_GATE", "done",
                         {"blocked": len(report.blocked_symbols),
                          "held": len(report.held_symbols),
                          "allowed": len(report.allowed_symbols)},
                         int((time.time() - t0) * 1000)))

    # --- Stage 4: Collision Scan ---
    t0 = time.time()
    all_mrs = list(open_mrs or [])
    # Add the current task as an MR if it has an mr_id
    task_mr = {"id": task.mr_id or task.task_id,
               "symbols": task.symbols_touched}
    # Only add if not already in the list
    existing_ids = {m.get("id") for m in all_mrs}
    if task_mr["id"] not in existing_ids:
        all_mrs.append(task_mr)

    collision_report = None
    if len(all_mrs) >= 2:
        collision_report = collision_mod.detect_collisions(graph, all_mrs)
    report.collision_report = collision_report

    if collision_report:
        report.merge_order = collision_report.get("merge_order")
        stages.append(_stage("COLLISION_SCAN", "done",
                             {"collisions": collision_report["counts"]["collisions"],
                              "colliding_mrs": collision_report["counts"]["colliding_mrs"]},
                             int((time.time() - t0) * 1000)))
    else:
        report.merge_order = [task_mr["id"]]
        stages.append(_stage("COLLISION_SCAN", "done",
                             {"collisions": 0, "colliding_mrs": 0},
                             int((time.time() - t0) * 1000)))

    # --- Stage 5: Overall Verdict ---
    t0 = time.time()
    worst = "ALLOW"
    for gr in gate_results:
        if _VERDICT_RANK.get(gr.verdict, 0) > _VERDICT_RANK.get(worst, 0):
            worst = gr.verdict
    # Collisions escalate: any collision -> at least HOLD
    if collision_report and collision_report["counts"]["collisions"] > 0:
        if _VERDICT_RANK.get(worst, 0) < _VERDICT_RANK["HOLD"]:
            worst = "HOLD"

    report.overall_verdict = worst

    # Orbit snapshot attestation
    try:
        snapshot_parts = []
        for gr in gate_results:
            if gr.impact:
                snapshot_parts.append(attest_mod.orbit_snapshot_sha256(gr.impact))
        if snapshot_parts:
            import hashlib
            combined = hashlib.sha256(
                "|".join(sorted(snapshot_parts)).encode()
            ).hexdigest()
            report.orbit_snapshot_sha256 = combined
    except Exception:
        pass

    stages.append(_stage("VERDICT", "done",
                         {"overall": worst,
                          "blocked": report.blocked_symbols,
                          "held": report.held_symbols},
                         int((time.time() - t0) * 1000)))

    report.pipeline_stages = stages
    return report


def run_sample_harness(graph, ledger: Ledger) -> HarnessReport:
    """Run the harness over the demo scenario (3 sample MRs).

    This is the deterministic demo that proves the pipeline works
    against the committed Orbit self-index. No server needed.
    """
    # Build the primary task (the "agent" MR under review)
    primary = SAMPLE_MRS[0]  # MR-204: the bot-authored change
    task = HarnessTask(
        task_id="harness-demo-001",
        agent_id=primary["agent"],
        agent_kind=AgentKind.BOT if primary["kind"] == "bot" else AgentKind.HUMAN,
        symbols_touched=primary["symbols"],
        files_changed=[primary["file"]],
        mr_id=primary["id"],
        change_id=f"demo-{primary['id']}",
    )

    # Other open MRs for collision detection
    other_mrs = [{"id": mr["id"], "symbols": mr["symbols"]}
                 for mr in SAMPLE_MRS[1:]]

    return run_harness(task, graph, ledger,
                       mode=HarnessMode.SAMPLE,
                       open_mrs=other_mrs,
                       dry_run=True)
