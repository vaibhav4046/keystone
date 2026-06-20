"""Harness CLI: command-line interface for the Engineering Harness.

Usage:
    python -m harness.cli --sample                  # Demo scenario
    python -m harness.cli --local --symbols foo bar  # Local symbols
    python -m harness.cli --sample --format markdown # Markdown output

The CLI wires the pipeline to the graph and ledger, runs the harness,
and outputs structured results. No server needed.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile

# Ensure repo root is importable
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from harness.models import HarnessTask, HarnessMode, AgentKind
from harness.pipeline import run_harness, run_sample_harness
from harness import report as report_mod
from core import graph as graph_mod, impact as impact_mod, seed as seed_mod
from core.audit import Ledger


def _init_graph(fixture: bool = False, graph_path: str = None):
    """Initialize the graph, preferring the committed self-index for real data."""
    self_graph = os.path.join(_ROOT, "data", "keystone_self_graph.duckdb")
    if graph_path:
        return graph_mod.Graph(path=graph_path)
    if not fixture and os.path.exists(self_graph):
        return graph_mod.Graph(path=self_graph)
    return graph_mod.Graph(prefer_live=not fixture)


def _init_ledger(fixture: bool = False):
    """Initialize the ledger, seeding if needed."""
    if fixture:
        ledger_path = os.path.join(tempfile.mkdtemp(), "harness_ledger.jsonl")
    else:
        ledger_path = os.environ.get("KEYSTONE_LEDGER_PATH") or \
            os.path.join(os.path.expanduser("~"), ".keystone", "harness_ledger.jsonl")
    led = Ledger(ledger_path)
    if not led.rows():
        g = _init_graph(fixture)
        for row in seed_mod.seed_rows_for(g):
            sig = impact_mod.blast_radius_signature(
                row["blast_radius_set"], row.get("epicenter_id"))
            led.append(
                actor=row["actor"], change_id=row["change_id"],
                target_symbols=row["target_symbols"],
                blast_radius_set=row["blast_radius_set"], signature=sig,
                decision=row["decision"], rationale=row["rationale"])
    return led


def cmd_sample(args):
    """Run the demo scenario against the committed fixture."""
    graph = _init_graph(fixture=args.fixture)
    ledger = _init_ledger(fixture=args.fixture)
    result = run_sample_harness(graph, ledger)

    if args.format == "json":
        print(report_mod.to_json(result))
    elif args.format == "markdown":
        md = report_mod.to_markdown(result)
        print(md)
    elif args.format == "mr-comment":
        print(report_mod.to_mr_comment(result))
    else:
        _print_summary(result)

    # Write artifacts
    if args.out or args.format in ("json", "markdown", "mr-comment"):
        out_dir = args.out or os.path.join(_ROOT, "SUBMISSION", "generated")
        written = report_mod.write_artifacts(result, out_dir)
        print(f"\nArtifacts written to: {out_dir}")
        for name, path in written.items():
            print(f"  {name}: {os.path.basename(path)}")

    return 0


def cmd_local(args):
    """Run the harness against local symbols."""
    if not args.symbols:
        print("ERROR: --symbols required for local mode")
        return 1

    graph = _init_graph(fixture=args.fixture, graph_path=args.graph)
    ledger = _init_ledger(fixture=args.fixture)

    task = HarnessTask(
        agent_id=args.agent or "local-dev",
        agent_kind=AgentKind(args.agent_kind) if args.agent_kind else AgentKind.HUMAN,
        symbols_touched=args.symbols,
        files_changed=args.files or [],
        mr_id=args.mr,
        change_id=args.change_id,
    )

    result = run_harness(task, graph, ledger,
                         mode=HarnessMode.LOCAL,
                         dry_run=not args.record)

    if args.format == "json":
        print(report_mod.to_json(result))
    elif args.format == "markdown":
        print(report_mod.to_markdown(result))
    else:
        _print_summary(result)

    return 0 if result.overall_verdict != "BLOCK" else 2


def _print_summary(result):
    """Print a compact terminal summary."""
    d = result.to_dict()
    task = d.get("task") or {}
    print(f"\n{'='*60}")
    print("KEYSTONE ENGINEERING HARNESS")
    print(f"{'='*60}")
    print(f"  Mode      : {d.get('mode', '?')}")
    print(f"  Agent     : {task.get('agent_id', '?')} ({task.get('agent_kind', '?')})")
    print(f"  MR        : {task.get('mr_id', 'N/A')}")
    print(f"  Verdict   : {d.get('overall_verdict', '?')}")
    print()

    # Pipeline stages
    print("  Pipeline:")
    for stage in d.get("pipeline_stages", []):
        ms = stage.get("duration_ms", "?")
        print(f"    {stage['name']:20s} {stage['status']:6s} ({ms}ms)")
    print()

    # Per-symbol results
    print("  Symbols:")
    for gr in d.get("gate_results", []):
        pol = gr.get("policy") or {}
        imp = gr.get("impact") or {}
        counts = imp.get("counts", {})
        print(f"    {gr['symbol']:30s} {gr['verdict']:6s} "
              f"tier={pol.get('tier', '?'):12s} "
              f"blast={counts.get('total_affected', 0)}")
    print()

    # Collision summary
    coll = d.get("collision_report")
    if coll:
        counts = coll.get("counts", {})
        print(f"  Collisions : {counts.get('collisions', 0)} across "
              f"{counts.get('mrs', 0)} MRs")
        order = d.get("merge_order")
        if order:
            print(f"  Merge order: {' -> '.join(order)}")
        print(f"  {coll.get('verdict', '')}")
    print(f"\n{'='*60}\n")


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="keystone-harness",
        description="Keystone Engineering Harness: deterministic governance "
                    "pipeline for agent-authored code changes.")

    sub = ap.add_subparsers(dest="command")

    # sample subcommand
    sp = sub.add_parser("sample", help="Run the demo scenario")
    sp.add_argument("--fixture", action="store_true",
                    help="Force the committed fixture graph (deterministic)")
    sp.add_argument("--format", choices=["summary", "json", "markdown", "mr-comment"],
                    default="summary")
    sp.add_argument("--out", default=None,
                    help="Output directory for artifacts")

    # local subcommand
    lp = sub.add_parser("local", help="Run against local symbols")
    lp.add_argument("--symbols", nargs="+", help="Symbols to evaluate")
    lp.add_argument("--files", nargs="+", help="Changed files")
    lp.add_argument("--mr", help="MR ID")
    lp.add_argument("--change-id", help="Change ID")
    lp.add_argument("--agent", help="Agent ID")
    lp.add_argument("--agent-kind", choices=["human", "bot", "ci"])
    lp.add_argument("--graph", help="Path to graph DuckDB")
    lp.add_argument("--fixture", action="store_true")
    lp.add_argument("--record", action="store_true",
                    help="Record decisions to the ledger (not dry-run)")
    lp.add_argument("--format", choices=["summary", "json", "markdown"],
                    default="summary")

    # Handle no subcommand -> default to sample
    args = ap.parse_args(argv)
    if not args.command:
        args.command = "sample"
        args.fixture = True
        args.format = "summary"
        args.out = None

    if args.command == "sample":
        return cmd_sample(args)
    elif args.command == "local":
        return cmd_local(args)
    else:
        ap.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
