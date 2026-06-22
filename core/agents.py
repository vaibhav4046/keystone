"""Agent-identity governance (deterministic, no inference).

The 2026 "who wrote this code" problem: autonomous coding agents open changes.
Keystone resolves the author against a repo-committed registry and, for a registered
agent, enforces a per-agent SCOPE MANIFEST (allowed/forbidden path globs + a maximum
blast radius) using exact set membership and fnmatch only. A change outside an
agent's scope is a hard SCOPE-VIOLATION. All matching is literal; there is no ML,
no fuzzy matching, and a registry miss is reported as detected-not-proven.

Source: .keystone/agents.json if present, else DEFAULT_REGISTRY. Standard library.
"""
from __future__ import annotations

import fnmatch
import json
import os
from typing import Optional

AGENTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".keystone", "agents.json")
AGENTS_PATH = os.path.abspath(AGENTS_PATH)

DEFAULT_REGISTRY = {
    "agents": {
        "claude-code": {
            "model": "claude-opus-4-8",
            "allowed_paths": ["/src/**"],
            "forbidden_paths": ["/src/cli/**", "**/config*.py"],
            "max_blast_radius": 6,
        }
    }
}


def load_registry() -> dict:
    if os.path.exists(AGENTS_PATH):
        try:
            with open(AGENTS_PATH, encoding="utf-8") as f:
                r = json.load(f)
            if isinstance(r, dict) and "agents" in r:
                return r
        except Exception:
            pass
    return DEFAULT_REGISTRY


def resolve_author(author: str, declared_kind: Optional[str] = None, registry: Optional[dict] = None) -> dict:
    """Resolve an author to an identity badge.

    The badge describes REGISTRATION against the committed manifest, never a proof of identity:
    the author name and declared_kind are self-asserted (see the README integrity note), so a
    match means "this name has a committed scope manifest", not "this caller is cryptographically
    this agent". The name is deliberately AGENT_REGISTERED, not AGENT_VERIFIED, to avoid claiming
    an identity guarantee the system does not provide.

    HUMAN               : not declared as an agent.
    AGENT_REGISTERED    : declared agent AND present in the committed registry (scope applies).
    AGENT_UNREGISTERED  : declared agent but not in the registry (detected, not proven).
    """
    registry = registry or load_registry()
    agents = registry.get("agents", {})
    if author in agents:
        a = agents[author]
        return {"id": author, "badge": "AGENT_REGISTERED", "model": a.get("model"),
                "scope": {"allowed_paths": a.get("allowed_paths", []),
                          "forbidden_paths": a.get("forbidden_paths", []),
                          "max_blast_radius": a.get("max_blast_radius")}}
    if (declared_kind or "").lower() == "agent":
        return {"id": author, "badge": "AGENT_UNREGISTERED", "model": None, "scope": None}
    return {"id": author, "badge": "HUMAN", "model": None, "scope": None}


def _changed_files(impact_dict: dict) -> list:
    """Files the change actually EDITS: the epicenter(s) at ring 0. Path scope governs what
    the agent changes, not what its change transitively affects; a dependent that merely lives
    in a forbidden path (ring 1+) must not flag a change made entirely within allowed paths,
    because the agent never edited it. The blast magnitude is governed separately by
    max_blast_radius. Falls back to all owned files only if no ring-0 epicenter file is present."""
    owners = impact_dict.get("owners", []) or []
    files = {o["file"] for o in owners if o.get("ring", 0) == 0 and o.get("file")}
    if not files:
        files = {o["file"] for o in owners if o.get("file")}
    return sorted(files)


def _matches(path: str, pattern: str) -> bool:
    """fnmatch that is robust to the leading-slash mismatch between the fixture
    (/src/**) and a real Orbit graph (relative src/...). Both sides are normalised
    so a forbidden pattern is never silently skipped on a real graph."""
    p = (path or "").lstrip("/")
    pat = (pattern or "").lstrip("/")
    return fnmatch.fnmatch(p, pat) or fnmatch.fnmatch("/" + p, pattern) or fnmatch.fnmatch(path or "", pattern)


def check_scope(author_ctx: dict, impact_dict: dict) -> dict:
    """For a registered agent, check the change against its scope manifest.
    Returns {in_scope, violations[]}. Non-agents / unregistered have no manifest,
    so they are not auto-blocked here (they fall under the normal human gate)."""
    scope = author_ctx.get("scope")
    if not scope:
        return {"in_scope": True, "violations": []}
    files = _changed_files(impact_dict)
    allowed = scope.get("allowed_paths") or []
    forbidden = scope.get("forbidden_paths") or []
    violations = []
    for f in files:
        if any(_matches(f, pat) for pat in forbidden):
            violations.append(f"{f} matches a forbidden path for this agent")
        elif allowed and not any(_matches(f, pat) for pat in allowed):
            violations.append(f"{f} is outside this agent's allowed paths")
    cap = scope.get("max_blast_radius")
    defs = int(impact_dict.get("counts", {}).get("total_affected", 0))
    if cap is not None and defs > cap:
        violations.append(f"blast radius {defs} exceeds this agent's max_blast_radius {cap}")
    return {"in_scope": not violations, "violations": violations}
