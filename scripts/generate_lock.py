"""Generate data/requirements.lock from THIS project's declared dependencies only.

Why not `pip freeze`: it captures the entire active environment (488 packages when
this was last run), including unrelated tooling, and it happily emits editable
installs as absolute local paths -- which would publish the maintainer's home
directory and the names of unrelated private projects into a public repository.

This walks requirements.txt, resolves each declared dependency against what is
actually installed, and writes only those. Anything not installed is reported
rather than guessed.
"""
from __future__ import annotations

import re
import sys
from importlib import metadata

ROOT = r"D:\project\keystone"
REQ = ROOT + r"\requirements.txt"
OUT = ROOT + r"\data\requirements.lock"

DECLARED = re.compile(r"^\s*([A-Za-z0-9._-]+)")

# importlib.metadata needs the distribution name, which is not always the import name.
DIST_FOR = {
    "google-genai": "google-genai",
    "uvicorn": "uvicorn",
    "tree_sitter": "tree_sitter",
    "tree_sitter_javascript": "tree_sitter_javascript",
    "tree_sitter_typescript": "tree_sitter_typescript",
}

declared, skipped = [], []
with open(REQ, encoding="utf-8") as fh:
    for raw in fh:
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        m = DECLARED.match(line)
        if m:
            declared.append(m.group(1))

rows, missing = [], []
for name in declared:
    dist = DIST_FOR.get(name, name)
    try:
        rows.append((name, metadata.version(dist)))
    except metadata.PackageNotFoundError:
        missing.append(name)

header = (
    "# Keystone dependency lock.\n"
    "#\n"
    "# Resolved from requirements.txt against the installed environment by\n"
    "# scripts/generate_lock.py. Scoped to this project's declared dependencies on\n"
    "# purpose: a full `pip freeze` would emit editable installs as absolute local\n"
    "# paths, publishing the maintainer's home directory and unrelated private\n"
    "# project names into a public repo, and would pin hundreds of packages that\n"
    "# have nothing to do with this project.\n"
    "#\n"
    "# Regenerate:  python scripts/generate_lock.py\n"
)

with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    fh.write(header)
    for name, ver in rows:
        fh.write(f"{name}=={ver}\n")

print(f"declared dependencies : {len(declared)}")
print(f"resolved and written  : {len(rows)}")
if missing:
    print(f"NOT installed (skipped, not guessed): {missing}")
print(f"wrote {OUT}")
for name, ver in rows:
    print(f"   {name}=={ver}")