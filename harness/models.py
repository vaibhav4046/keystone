"""Harness data models: pure dataclasses, no ORM, no Pydantic.

These are the typed structures the pipeline passes between stages.
Every field is deterministic and traceable to a real graph computation.
"""
from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import List, Optional


class HarnessMode(enum.Enum):
    """Pipeline execution mode."""
    SAMPLE = "sample"       # Demo scenario against committed fixture
    LOCAL = "local"         # Local diff against live/fixture graph
    GITLAB_MR = "gitlab_mr" # Read changed files from a GitLab MR API


class AgentKind(enum.Enum):
    """Who authored the change."""
    HUMAN = "human"
    BOT = "bot"             # Coding agent (Codex, Copilot, Devin, etc.)
    CI = "ci"               # CI pipeline auto-fix


@dataclass
class HarnessTask:
    """A unit of work submitted to the harness for governance review.

    Represents one agent patch or MR that touches specific symbols.
    """
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_id: str = "unknown-agent"
    agent_kind: AgentKind = AgentKind.BOT
    symbols_touched: List[str] = field(default_factory=list)
    files_changed: List[str] = field(default_factory=list)
    mr_id: Optional[str] = None
    change_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "agent_kind": self.agent_kind.value,
            "symbols_touched": self.symbols_touched,
            "files_changed": self.files_changed,
            "mr_id": self.mr_id,
            "change_id": self.change_id or self.task_id,
            "timestamp": self.timestamp,
        }


@dataclass
class HarnessGateResult:
    """Gate evaluation result for a single symbol."""
    symbol: str
    found: bool = True
    impact: Optional[dict] = None       # Impact.to_dict()
    policy: Optional[dict] = None       # policy.evaluate()
    precedent: Optional[dict] = None    # ledger.precedent()
    verdict: str = "ALLOW"              # ALLOW | HOLD | BLOCK
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "found": self.found,
            "impact": self.impact,
            "policy": self.policy,
            "precedent": self.precedent,
            "verdict": self.verdict,
            "reasons": self.reasons,
        }


@dataclass
class HarnessReport:
    """Complete harness pipeline output for one task."""
    task: Optional[HarnessTask] = None
    mode: HarnessMode = HarnessMode.SAMPLE
    gate_results: List[HarnessGateResult] = field(default_factory=list)
    collision_report: Optional[dict] = None     # collision.detect_collisions()
    merge_order: Optional[list] = None
    overall_verdict: str = "ALLOW"              # worst of individual verdicts
    ledger_rows_appended: int = 0
    orbit_snapshot_sha256: Optional[str] = None
    pipeline_stages: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "task": self.task.to_dict() if self.task else None,
            "mode": self.mode.value,
            "gate_results": [g.to_dict() for g in self.gate_results],
            "collision_report": self.collision_report,
            "merge_order": self.merge_order,
            "overall_verdict": self.overall_verdict,
            "ledger_rows_appended": self.ledger_rows_appended,
            "orbit_snapshot_sha256": self.orbit_snapshot_sha256,
            "pipeline_stages": self.pipeline_stages,
        }

    @property
    def blocked_symbols(self) -> List[str]:
        return [g.symbol for g in self.gate_results if g.verdict == "BLOCK"]

    @property
    def held_symbols(self) -> List[str]:
        return [g.symbol for g in self.gate_results if g.verdict == "HOLD"]

    @property
    def allowed_symbols(self) -> List[str]:
        return [g.symbol for g in self.gate_results if g.verdict == "ALLOW"]
