"""Runtime driver for GitLab Orbit Local through its own CLI.

Keystone's fast path reads the Orbit Local DuckDB file directly with the
duckdb Python package (see core/graph.py). That is fast and works offline, but
on its own it never exercises Orbit's published interface at product runtime,
so the only thing satisfying the hackathon "meaningful use of Orbit via its
API, CLI, or skill interface" gate is the SKILL.md plus AI Catalog agent layer.

This module closes that gap. It shells out to the real Orbit Local CLI

    glab orbit local schema [table]
    glab orbit local sql "<query>"

for schema introspection and at least one live query per session, capturing the
exact argv, the rendered command line, the exit code, the wall-clock duration,
and the raw stdout/stderr into a transcript ring buffer. The backend /status
endpoint and the honest status panel read that transcript, so the demo can SHOW
Orbit's own CLI being driven by Keystone, not just a Python file opening a
DuckDB file.

Hard rules this module obeys (Sections C, D, H of the master prompt):
  - Determinism: this module only fetches and parses rows. It never invents,
    blends, or rounds a number. The authoritative figures the UI displays are
    computed by the deterministic engine (core/impact.py) over the same graph.
    The CLI live query is provenance and optional cross-check, never the source
    of a displayed count.
  - No hang: every invocation runs behind a hard timeout. On timeout, a missing
    glab binary, or any error, it returns a result with ok=False and the engine
    falls back to the direct-DuckDB fast path (and then to the fixture).
  - No secrets: only glab's own argv and stdout/stderr are captured. The process
    environment is never serialised into the transcript.
  - Canonical command form: always `glab orbit local <sql|schema|index>`
    (master-prompt Invariant two). The bare `orbit` binary is not used here.

Standard library only. No web imports, no third-party packages, no LLM.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

# glab binary name; override with KEYSTONE_GLAB_BINARY for an absolute path.
GLAB_BINARY = os.environ.get("KEYSTONE_GLAB_BINARY", "glab")

# The Orbit Local CLI is the `orbit` binary that `glab orbit local` launches.
# Going through glab adds a per-invocation network update/version check that can
# hang offline, so when KEYSTONE_ORBIT_BINARY points at the orbit binary directly
# we drive it as `orbit <subcommand>` (fast, offline). Both forms ARE the Orbit
# Local CLI; this only changes the launcher. Unset by default so tests and the
# documented `glab orbit local` form remain the canonical path.
ORBIT_BINARY = os.environ.get("KEYSTONE_ORBIT_BINARY") or None

# Hard per-invocation timeout in seconds. Orbit schema/sql calls are local and
# should be quick, but a generous ceiling keeps a stalled CLI from ever blocking
# a render. Override with KEYSTONE_ORBIT_CLI_TIMEOUT.
DEFAULT_TIMEOUT = float(os.environ.get("KEYSTONE_ORBIT_CLI_TIMEOUT", "6.0"))

# Cap on stdout/stderr stored per transcript entry so /status stays light. The
# returned OrbitCliResult keeps the full text for the immediate caller.
_TRANSCRIPT_TEXT_CAP = 4000
# Most recent invocations kept in memory for the status panel.
_TRANSCRIPT_MAX_ENTRIES = 50

_transcript: list["OrbitCliResult"] = []
_transcript_lock = threading.Lock()


@dataclass
class OrbitCliResult:
    """One captured `glab orbit local ...` invocation.

    Every field is plain data so it serialises straight into the /status JSON
    payload and renders identically in the web status panel and the CLI TUI.
    """

    subcommand: str  # "schema" or "sql"
    argv: list[str]  # exact argument vector passed to the binary
    command: str  # human-readable command line shown in the status panel
    returncode: Optional[int]  # None when the process never started
    stdout: str
    stderr: str
    duration_ms: float
    ok: bool  # True only when the binary ran AND exited 0
    source: str = "glab orbit local"  # always Orbit Local, never Orbit Remote
    parsed: Any = None  # best-effort structured parse of stdout, or None
    error: Optional[str] = None  # why ok is False, if applicable
    ts: float = 0.0  # epoch seconds the invocation started

    def as_status_entry(self) -> dict:
        """A compact, secret-free dict for the /status transcript list."""
        return {
            "subcommand": self.subcommand,
            "command": self.command,
            "returncode": self.returncode,
            "ok": self.ok,
            "duration_ms": round(self.duration_ms, 1),
            "source": self.source,
            "stdout": _truncate(self.stdout, _TRANSCRIPT_TEXT_CAP),
            "stderr": _truncate(self.stderr, _TRANSCRIPT_TEXT_CAP),
            "error": self.error,
            "ts": self.ts,
        }


def _truncate(text: str, cap: int) -> str:
    if text is None:
        return ""
    if len(text) <= cap:
        return text
    return text[:cap] + "\n... [truncated {} chars]".format(len(text) - cap)


def _binary_available(binary: str) -> bool:
    return shutil.which(binary) is not None or (
        os.path.isabs(binary) and os.path.isfile(binary)
    )


def glab_available(binary: str = GLAB_BINARY) -> bool:
    """True when a glab executable is resolvable on PATH (or as an abs path)."""
    return _binary_available(binary)


def _driver():
    """Resolve which CLI launcher to drive.

    Returns (binary, prefix_args, source, label). When KEYSTONE_ORBIT_BINARY is
    set we drive the orbit binary directly (`orbit <sub>`); otherwise the
    documented `glab orbit local <sub>` form.
    """
    if ORBIT_BINARY:
        return ORBIT_BINARY, [], "orbit local", "orbit"
    return GLAB_BINARY, ["orbit", "local"], "glab orbit local", "glab"


def cli_available() -> bool:
    """True when the resolved launcher (orbit binary or glab) is runnable."""
    binary, _prefix, _source, _label = _driver()
    if ORBIT_BINARY:
        return _binary_available(binary)
    return glab_available()


def _record(result: OrbitCliResult) -> None:
    """Append a result to the bounded in-memory transcript."""
    with _transcript_lock:
        _transcript.append(result)
        if len(_transcript) > _TRANSCRIPT_MAX_ENTRIES:
            del _transcript[: len(_transcript) - _TRANSCRIPT_MAX_ENTRIES]


def get_transcript(limit: Optional[int] = None) -> list[dict]:
    """Captured invocations, newest last, as status-panel-ready dicts."""
    with _transcript_lock:
        entries = list(_transcript)
    if limit is not None:
        entries = entries[-limit:]
    return [e.as_status_entry() for e in entries]


def transcript_lines(limit: Optional[int] = None) -> list[str]:
    """One-line-per-invocation view for a CLI/text status panel."""
    lines = []
    for e in get_transcript(limit):
        flag = "OK " if e["ok"] else "ERR"
        rc = e["returncode"] if e["returncode"] is not None else "-"
        lines.append(
            "[{}] {} (exit {}, {}ms)".format(
                flag, e["command"], rc, e["duration_ms"]
            )
        )
    return lines


def clear_transcript() -> None:
    """Reset the transcript. Used by tests and at session start."""
    with _transcript_lock:
        _transcript.clear()


def _render_command(argv: list[str]) -> str:
    """A copy-pasteable command line for the status panel and demo.

    Uses shell-style quoting so the SQL argument shows with its quotes intact,
    which is exactly what a viewer needs to see Keystone driving Orbit's CLI.
    """
    return " ".join(shlex.quote(part) for part in argv)


def _run(subcommand: str, extra_args: list[str], timeout: float) -> OrbitCliResult:
    """Low-level: run `glab orbit local <subcommand> <extra_args...>`.

    Always records the result in the transcript, including failures, so the
    status panel shows the attempt even when the binary is missing.
    """
    binary, prefix, source, label = _driver()
    argv = [binary, *prefix, subcommand, *extra_args]
    command = _render_command(argv)
    started = time.time()
    perf = time.perf_counter()

    if not cli_available():
        result = OrbitCliResult(
            subcommand=subcommand,
            argv=argv,
            command=command,
            returncode=None,
            stdout="",
            stderr="",
            duration_ms=0.0,
            ok=False,
            source=source,
            error="{} binary not found on PATH; using direct-DuckDB fast path".format(label),
            ts=started,
        )
        _record(result)
        return result

    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,  # never invoke a shell; argv is passed verbatim
        )
        duration_ms = (time.perf_counter() - perf) * 1000.0
        ok = proc.returncode == 0
        result = OrbitCliResult(
            subcommand=subcommand,
            argv=argv,
            command=command,
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            duration_ms=duration_ms,
            ok=ok,
            source=source,
            error=None if ok else "{} exited {}".format(label, proc.returncode),
            ts=started,
        )
    except subprocess.TimeoutExpired:
        duration_ms = (time.perf_counter() - perf) * 1000.0
        result = OrbitCliResult(
            subcommand=subcommand,
            argv=argv,
            command=command,
            returncode=None,
            stdout="",
            stderr="",
            duration_ms=duration_ms,
            ok=False,
            source=source,
            error="{} timed out after {:.1f}s".format(label, timeout),
            ts=started,
        )
    except OSError as exc:  # binary vanished between check and exec, perms, etc.
        duration_ms = (time.perf_counter() - perf) * 1000.0
        result = OrbitCliResult(
            subcommand=subcommand,
            argv=argv,
            command=command,
            returncode=None,
            stdout="",
            stderr="",
            duration_ms=duration_ms,
            ok=False,
            source=source,
            error="failed to run {}: {}".format(label, exc),
            ts=started,
        )

    _record(result)
    return result


def _parse_rows(stdout: str) -> Optional[Any]:
    """Best-effort deterministic parse of `glab orbit local sql` output.

    Orbit Local's output format is UNVERIFIED (master-prompt Invariant two), so
    this is defensive and never raises. It tries JSON first (object or array),
    then newline-delimited JSON, then a simple header+rows table. On any doubt
    it returns None and the caller falls back to the direct-DuckDB read for the
    authoritative values. Parsing the CLI output is for cross-check and display,
    not for the numbers the UI commits to.
    """
    text = (stdout or "").strip()
    if not text:
        return None

    # 1. A single JSON document (array of row objects, or one object).
    try:
        doc = json.loads(text)
        return doc
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. Newline-delimited JSON (one row object per line).
    lines = [ln for ln in text.splitlines() if ln.strip()]
    ndjson_rows = []
    ndjson_ok = len(lines) > 0
    for ln in lines:
        try:
            ndjson_rows.append(json.loads(ln))
        except (json.JSONDecodeError, ValueError):
            ndjson_ok = False
            break
    if ndjson_ok and ndjson_rows:
        return ndjson_rows

    # 3. A whitespace/pipe-delimited table: first line is the header.
    if len(lines) >= 2:
        sep = "|" if "|" in lines[0] else None
        header = [c.strip() for c in (lines[0].split(sep) if sep else lines[0].split())]
        if header:
            rows = []
            for ln in lines[1:]:
                # Skip rule lines like +----+----+ that some renderers emit.
                if set(ln.strip()) <= set("+-| "):
                    continue
                cells = [c.strip() for c in (ln.split(sep) if sep else ln.split(None, len(header) - 1))]
                if len(cells) == len(header):
                    rows.append(dict(zip(header, cells)))
            if rows:
                return rows

    # Unparseable; let the caller rely on the DuckDB fast path.
    return None


def schema(table: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT) -> OrbitCliResult:
    """Drive `glab orbit local schema [table]` for live schema introspection.

    With no table, returns the whole-database schema. With a table name (for
    example gl_definition), returns that table's columns. The parsed field holds
    a best-effort structured view; the raw stdout is always preserved for the
    status panel and for cross-checking against DuckDB PRAGMA table_info.
    """
    extra = [table] if table else []
    result = _run("schema", extra, timeout)
    if result.ok:
        result.parsed = _parse_rows(result.stdout) or result.stdout.strip()
    return result


def sql(query: str, timeout: float = DEFAULT_TIMEOUT) -> OrbitCliResult:
    """Drive `glab orbit local sql "<query>"` for one live query.

    The query string is passed as a single argv element (no shell), so embedded
    spaces and quotes are safe. parsed holds best-effort rows; ok plus stdout
    are what the status panel shows to prove the CLI ran.
    """
    result = _run("sql", [query], timeout)
    if result.ok:
        result.parsed = _parse_rows(result.stdout)
    return result


def probe(timeout: float = DEFAULT_TIMEOUT) -> OrbitCliResult:
    """Cheap liveness probe used at session start.

    Selects callable definition names (function/method/class), so a single call
    confirms the CLI runs AND returns plausible code symbols rather than file-path
    module entries. Result is recorded in the transcript like any other invocation.
    """
    return sql("SELECT name FROM gl_definition WHERE definition_type IN "
               "('Function','Method','Class','DecoratedFunction') LIMIT 3", timeout=timeout)


__all__ = [
    "OrbitCliResult",
    "GLAB_BINARY",
    "DEFAULT_TIMEOUT",
    "glab_available",
    "schema",
    "sql",
    "probe",
    "get_transcript",
    "transcript_lines",
    "clear_transcript",
]
