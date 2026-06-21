"""Map a unified diff (git diff / MR patch) to the symbols it changes.

This closes the autonomous-gate gap: instead of a human naming the colliding
symbols by hand (`shadow-merge --a X --b Y`), Keystone reads a real diff, finds
every gl_definition whose [start_line, end_line] intersects a changed line on the
new side, and feeds those symbols straight into the blast-radius / collision gate.

Pure + deterministic; reads only gl_definition. No new dependencies.
"""
from __future__ import annotations

import re
from typing import Dict, List, Set

# +++ b/path  and  @@ -a,b +c,d @@  hunk headers of a unified diff
_NEWFILE = re.compile(r"^\+\+\+\s+(.+)$")
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def parse_diff(diff_text: str) -> Dict[str, Set[int]]:
    """Return {new_file_path: {changed new-side line numbers}} from a unified diff.

    Tracks the running new-side line cursor across hunks; an added ('+') or context
    line advances/records it, a removed ('-') line does not consume a new-side line.
    """
    files: Dict[str, Set[int]] = {}
    cur: str | None = None
    new_ln = 0
    for line in diff_text.splitlines():
        mnew = _NEWFILE.match(line)
        if mnew:
            p = mnew.group(1).strip().split("\t")[0]
            if p.startswith("b/"):
                p = p[2:]
            if p == "/dev/null":
                cur = None
            else:
                cur = p
                files.setdefault(cur, set())
            continue
        if line.startswith("--- "):
            continue
        mh = _HUNK.match(line)
        if mh:
            new_ln = int(mh.group(1))
            continue
        if cur is None:
            continue
        if line.startswith("+"):
            files[cur].add(new_ln)
            new_ln += 1
        elif line.startswith("-"):
            continue
        elif line.startswith("\\"):  # "\ No newline at end of file"
            continue
        else:  # context line
            new_ln += 1
    return {f: lines for f, lines in files.items() if lines}


def _path_match(index_path: str, diff_path: str) -> bool:
    """A diff path is repo-root-relative; an index path may carry an absolute-ish
    root. Match when either is a suffix of the other (basename-anchored)."""
    a = str(index_path).replace("\\", "/").lstrip("./")
    b = str(diff_path).replace("\\", "/").lstrip("./")
    return a == b or a.endswith("/" + b) or b.endswith("/" + a)


def changed_symbols(graph, diff_text: str) -> List[dict]:
    """Resolve a diff to the changed gl_definition rows.

    Returns a de-duplicated, stably-ordered list of
    {id, name, fqn, file_path, definition_type}: every definition whose line range
    intersects a changed line in the matching file.
    """
    by_file = parse_diff(diff_text)
    if not by_file:
        return []
    rows = graph._con.execute(
        "SELECT id, name, fqn, file_path, definition_type, start_line, end_line "
        "FROM gl_definition WHERE start_line IS NOT NULL AND end_line IS NOT NULL"
    ).fetchall()
    out: Dict[int, dict] = {}
    for did, name, fqn, fpath, dtype, s, e in rows:
        try:
            lo, hi = int(s), int(e)
        except (TypeError, ValueError):
            continue
        for dfile, lines in by_file.items():
            if not _path_match(fpath, dfile):
                continue
            if any(lo <= ln <= hi for ln in lines):
                out[did] = {"id": did, "name": name, "fqn": fqn,
                            "file_path": fpath, "definition_type": dtype}
                break
    return sorted(out.values(), key=lambda r: (str(r["file_path"]), str(r["name"]), r["id"]))
