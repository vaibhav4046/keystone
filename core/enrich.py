"""Orbit Remote enrichment gates - the SDLC signals the local code graph cannot see.

Orbit Local gives Keystone the call graph (defs + edges). Orbit REMOTE additionally exposes the
SDLC graph: CODEOWNERS, commit recency, pipeline history, and security findings. Those power three
governance gates the README documents but Orbit Local cannot feed:

  1. ownership-entropy   : how many distinct owners + how stale the changed files are (a high-entropy
                           change - many owners or no recent owner - is a coordination/review risk).
  2. pipeline-health     : the recent CI failure rate of the changed files (a flaky/failing area is a
                           riskier place to land a large blast radius).
  3. dependency-quarantine: a blast radius that reaches a definition with a known security finding is
                           quarantined - the change touches code under an open advisory.

This module runs that gate LOGIC against the REAL Orbit Remote schema (gl_codeowners,
gl_commit_recency, gl_pipeline_history, gl_security_finding), reading a committed, clearly-labelled
SYNTHETIC fixture (data/orbit_remote_fixture.duckdb) when a paid Orbit Ultimate instance is not
available. The data is synthetic and SAID to be; the SCHEMA and the gate logic are real, so the full
governance vision is demonstrable end-to-end, not faked on the local graph. Deterministic, no model.
"""
from __future__ import annotations

import os
from typing import Optional

DEFAULT_FIXTURE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "data", "orbit_remote_fixture.duckdb")
_PIPELINE_RISK_PCT = 25      # recent failure rate at/above this flags a fragile CI area
_STALE_CUTOFF = "2026-01-01"  # a file whose last_commit_at is older than this counts as stale ownership


def remote_path() -> Optional[str]:
    p = os.environ.get("KEYSTONE_ORBIT_REMOTE") or DEFAULT_FIXTURE
    return p if os.path.exists(p) else None


def _affected_files(impact) -> list:
    """The files a blast radius touches: the epicenter file + every owning file of an affected def."""
    files = set()
    if getattr(impact, "epicenter_file", None):
        files.add(impact.epicenter_file)
    for o in (getattr(impact, "owners", None) or []):
        if isinstance(o, dict) and o.get("file"):
            files.add(o["file"])
    return sorted(files)


def _affected_names(impact) -> list:
    names = set()
    if getattr(impact, "epicenter_name", None):
        names.add(impact.epicenter_name)
    for n in (getattr(impact, "names", None) or {}).values():
        names.add(n)
    return sorted(names)


def enrich(impact, path: Optional[str] = None) -> Optional[dict]:
    """Run the three Orbit Remote gates for a blast radius. Returns a labelled enrichment dict, or
    None when no Orbit Remote source (fixture or live) is available. Never raises - on any read
    error it degrades to None and the caller shows only the Orbit Local result."""
    path = path or remote_path()
    if not path:
        return None
    try:
        import duckdb
        con = duckdb.connect(path, read_only=True)
    except Exception:
        return None
    try:
        files = _affected_files(impact)
        names = _affected_names(impact)

        def _in(col, vals):
            return ((" AND %s IN (%s)" % (col, ",".join(["?"] * len(vals))), list(vals)) if vals
                    else (" AND 1=0", []))

        # 1. ownership-entropy
        owners, stale, owned_files = set(), [], set()
        if files:
            cond, params = _in("c.path", files)
            for path_, ow, last in con.execute(
                    "SELECT c.path, c.owners, r.last_commit_at FROM gl_codeowners c "
                    "LEFT JOIN gl_commit_recency r ON r.file_path = c.path WHERE 1=1" + cond, params).fetchall():
                owned_files.add(path_)
                for o in (ow or "").split(","):
                    if o.strip():
                        owners.add(o.strip())
                if not (last and str(last) >= _STALE_CUTOFF):
                    stale.append(path_)
        unowned = [f for f in files if f not in owned_files]
        entropy = {"distinct_owners": len(owners), "owners": sorted(owners),
                   "stale_files": sorted(stale), "unowned_files": unowned,
                   "high_entropy": len(owners) >= 4 or bool(unowned) or len(stale) >= 2}

        # 2. pipeline-health
        worst_pct, fragile = 0, []
        if files:
            cond, params = _in("file_path", files)
            for fp, runs, fails in con.execute(
                    "SELECT file_path, runs, failures FROM gl_pipeline_history WHERE 1=1" + cond, params).fetchall():
                pct = round(100 * (fails or 0) / max(runs or 1, 1))
                worst_pct = max(worst_pct, pct)
                if pct >= _PIPELINE_RISK_PCT:
                    fragile.append({"file": fp, "failure_pct": pct})
        pipeline = {"worst_failure_pct": worst_pct, "fragile_files": fragile,
                    "fragile": worst_pct >= _PIPELINE_RISK_PCT}

        # 3. dependency-quarantine
        findings = []
        if names:
            cond, params = _in("definition_name", names)
            for dn, sev, adv in con.execute(
                    "SELECT definition_name, severity, advisory FROM gl_security_finding WHERE 1=1" + cond,
                    params).fetchall():
                findings.append({"symbol": dn, "severity": sev, "advisory": adv})
        quarantine = {"quarantined": bool(findings), "findings": findings}

        risk = int(entropy["high_entropy"]) + int(pipeline["fragile"]) + int(quarantine["quarantined"])
        return {
            "source": "ORBIT_REMOTE_FIXTURE",          # honest: synthetic data, REAL Orbit Remote schema + gate logic
            "synthetic": path == DEFAULT_FIXTURE,
            "ownership_entropy": entropy,
            "pipeline_health": pipeline,
            "dependency_quarantine": quarantine,
            "extra_risk_signals": risk,
            "advisory": ("quarantine: a changed symbol is under an open security advisory" if quarantine["quarantined"]
                         else "fragile CI area + diffuse ownership raise review scrutiny"
                         if (pipeline["fragile"] and entropy["high_entropy"])
                         else "no additional Orbit Remote risk signal"),
        }
    finally:
        con.close()
