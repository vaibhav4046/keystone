"""Harness report generation: JSON, Markdown, and GitLab MR comment output.

Transforms a HarnessReport into structured artifacts that can be:
- Baked into data.json for the frontend
- Written to SUBMISSION/generated/ for hackathon submission
- Posted as a GitLab MR comment
"""
from __future__ import annotations

import json
import os

from .models import HarnessReport


def to_json(report: HarnessReport, *, indent: int = 2) -> str:
    """Serialize a HarnessReport to JSON."""
    return json.dumps(report.to_dict(), indent=indent, sort_keys=False,
                      ensure_ascii=False)


def to_markdown(report: HarnessReport) -> str:
    """Render a HarnessReport as a human-readable Markdown document."""
    lines = []
    d = report.to_dict()
    task = d.get("task") or {}

    lines.append("# Keystone Engineering Harness Report")
    lines.append("")
    lines.append(f"**Mode:** {d.get('mode', 'sample')}")
    lines.append(f"**Overall Verdict:** {d.get('overall_verdict', 'ALLOW')}")
    if task:
        lines.append(f"**Agent:** {task.get('agent_id', '?')} ({task.get('agent_kind', '?')})")
        lines.append(f"**MR:** {task.get('mr_id', 'N/A')}")
        lines.append(f"**Symbols touched:** {', '.join(task.get('symbols_touched', []))}")
    lines.append("")

    # Pipeline stages
    lines.append("## Pipeline Stages")
    lines.append("")
    lines.append("| Stage | Status | Detail |")
    lines.append("|-------|--------|--------|")
    for stage in d.get("pipeline_stages", []):
        detail_parts = []
        for k, v in (stage.get("detail") or {}).items():
            if isinstance(v, list):
                detail_parts.append(f"{k}: {', '.join(str(x) for x in v) if v else 'none'}")
            else:
                detail_parts.append(f"{k}: {v}")
        detail_str = "; ".join(detail_parts) if detail_parts else "-"
        ms = stage.get("duration_ms")
        status = stage.get("status", "?")
        if ms is not None:
            status += f" ({ms}ms)"
        lines.append(f"| {stage.get('name', '?')} | {status} | {detail_str} |")
    lines.append("")

    # Per-symbol verdicts
    lines.append("## Per-Symbol Verdicts")
    lines.append("")
    for gr in d.get("gate_results", []):
        verdict = gr.get("verdict", "?")
        badge = {"ALLOW": "ALLOW", "HOLD": "HOLD", "BLOCK": "**BLOCK**"}.get(verdict, verdict)
        lines.append(f"### `{gr.get('symbol', '?')}` - {badge}")
        lines.append("")
        if not gr.get("found"):
            lines.append("Symbol not found in the Orbit graph.")
            lines.append("")
            continue
        imp = gr.get("impact") or {}
        counts = imp.get("counts", {})
        lines.append(f"- Ring-1 (direct dependents): **{counts.get('ring_1', 0)}**")
        lines.append(f"- Total affected: **{counts.get('total_affected', 0)}**")
        pol = gr.get("policy") or {}
        lines.append(f"- Policy tier: **{pol.get('tier', '?')}**")
        lines.append(f"- Required approvers: **{pol.get('required_approvers', 1)}**")
        reasons = gr.get("reasons", [])
        if reasons:
            lines.append(f"- Reasons: {'; '.join(reasons)}")
        lines.append("")

    # Collision report
    coll = d.get("collision_report")
    if coll:
        lines.append("## Cross-MR Collision Analysis")
        lines.append("")
        counts = coll.get("counts", {})
        lines.append(f"- MRs analyzed: **{counts.get('mrs', 0)}**")
        lines.append(f"- Collisions found: **{counts.get('collisions', 0)}**")
        lines.append(f"- Colliding MRs: **{counts.get('colliding_mrs', 0)}**")
        lines.append("")
        for c in coll.get("collisions", []):
            kind = c.get("kind", "?")
            lines.append(f"**{c.get('mr_a', '?')} x {c.get('mr_b', '?')}** - "
                         f"{kind} (severity: {c.get('severity', 0)})")
            if c.get("shared"):
                lines.append(f"  Shared symbols: {', '.join(c['shared'])}")
            lines.append("")

        order = d.get("merge_order")
        if order:
            lines.append(f"**Safe merge order:** {' -> '.join(order)}")
            lines.append("")
        lines.append(f"**Verdict:** {coll.get('verdict', '')}")
        lines.append("")

    # Attestation
    sha = d.get("orbit_snapshot_sha256")
    if sha:
        lines.append("## Orbit Snapshot Attestation")
        lines.append("")
        lines.append(f"Combined snapshot SHA-256: `{sha[:16]}...`")
        lines.append("")

    lines.append("---")
    lines.append("_Engine computed from the Orbit code graph. "
                 "AI explains; the deterministic gate decides._")
    lines.append("")
    return "\n".join(lines)


def to_mr_comment(report: HarnessReport) -> str:
    """Render a concise GitLab MR review comment from the harness report."""
    d = report.to_dict()
    task = d.get("task") or {}
    overall = d.get("overall_verdict", "ALLOW")

    lines = []
    verb = {"BLOCK": "BLOCK", "HOLD": "HOLD", "ALLOW": "ALLOW"}.get(overall, overall)
    lines.append(f"## Keystone Harness: {verb}")
    lines.append("")

    agent_tag = ""
    if task.get("agent_kind") == "bot":
        agent_tag = f" (agent: `{task.get('agent_id', '?')}`)"
    lines.append(f"This MR (`{task.get('mr_id', '?')}`) changes "
                 f"{len(task.get('symbols_touched', []))} symbol(s){agent_tag}.")
    lines.append("")

    # Compact per-symbol table
    lines.append("| Symbol | Tier | Blast | Verdict |")
    lines.append("|--------|------|-------|---------|")
    for gr in d.get("gate_results", []):
        pol = gr.get("policy") or {}
        imp = gr.get("impact") or {}
        counts = imp.get("counts", {})
        lines.append(
            f"| `{gr.get('symbol', '?')}` "
            f"| {pol.get('tier', '?')} "
            f"| {counts.get('total_affected', 0)} defs "
            f"| **{gr.get('verdict', '?')}** |"
        )
    lines.append("")

    # Collision summary
    coll = d.get("collision_report")
    if coll and coll.get("counts", {}).get("collisions", 0) > 0:
        lines.append(f"**Cross-MR collisions:** {coll['counts']['collisions']} found. "
                     f"Safe merge order: {' -> '.join(d.get('merge_order', []))}")
        lines.append("")

    # Verdict reasons
    blocked = [gr for gr in d.get("gate_results", []) if gr.get("verdict") == "BLOCK"]
    if blocked:
        lines.append("**Why Keystone blocked:**")
        lines.append("")
        for gr in blocked:
            for r in gr.get("reasons", []):
                lines.append(f"- `{gr['symbol']}`: {r}")
        lines.append("")
        lines.append("**Required action:** Resolve the precedent or obtain owner approval "
                     "before merging.")
    elif overall == "HOLD":
        lines.append("**Why Keystone held:** Policy tier requires additional approvers "
                     "or review window.")
    else:
        lines.append("**Keystone approved:** All symbols within safe blast radius and "
                     "no contradicting precedent found.")
    lines.append("")

    lines.append("---")
    lines.append("_Keystone Engineering Harness. Engine computed from the Orbit graph. "
                 "Same graph + same policy = same decision._")
    lines.append("")
    return "\n".join(lines)


def write_artifacts(report: HarnessReport, output_dir: str) -> dict:
    """Write all harness artifacts to the output directory.

    Returns a dict of {name: path} for each written file.
    """
    os.makedirs(output_dir, exist_ok=True)
    written = {}

    # JSON report
    json_path = os.path.join(output_dir, "harness_report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(to_json(report))
    written["json"] = json_path

    # Markdown report
    md_path = os.path.join(output_dir, "harness_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(to_markdown(report))
    written["markdown"] = md_path

    # MR comment
    comment_path = os.path.join(output_dir, "harness_mr_comment.md")
    with open(comment_path, "w", encoding="utf-8") as f:
        f.write(to_mr_comment(report))
    written["mr_comment"] = comment_path

    return written
