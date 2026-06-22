"""Build an Orbit-shaped graph from ANY repo with zero pre-indexing.

The gate normally needs a pre-existing Orbit DuckDB (GitLab Ultimate + Orbit Local),
which pins the addressable market. This builds the SAME gl_definition / gl_edge / gl_file
/ gl_directory schema the engine consumes - on the fly, from plain Python source - using
the stdlib `ast` (accurate defs + line ranges + call edges, better than a regex pass).
So `scan-repo owner/repo` turns "a control a tiny slice of orgs can run" into "a CI gate
any team can drop in today", over the same deterministic engine.

Call resolution is name-based (a def calls another def of the same name in the repo) -
the honest call-graph approximation Orbit and the in-browser analyzer also concede
(dynamic dispatch is under-approximated).
"""
from __future__ import annotations

import ast
import json as _json
import os
import re
import tempfile
import urllib.request as _urequest
from typing import Dict, List, Optional, Tuple

MAX_FILES = 400
MAX_FILE_BYTES = 300_000
# Match the capitalized Orbit vocabulary the graph filters on (core/graph.py CALLABLE_TYPES);
# lowercase values silently miss every WHERE definition_type IN (...) query on a scanned graph.
_DEF_TYPES = {"FunctionDef": "Function", "AsyncFunctionDef": "Function", "ClassDef": "Class"}

# Multi-language: Python is parsed with ast (accurate); JS/TS with a name-based regex pass
# (the same honest approximation Orbit concedes - dynamic dispatch is under-approximated).
_JS_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
_SOURCE_EXT = {".py"} | _JS_EXT
_LANG = {".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript",
         ".cjs": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript"}
_JS_KEYWORDS = {"if", "for", "while", "switch", "catch", "return", "function", "typeof",
                "await", "new", "delete", "void", "do", "else", "case", "yield", "super",
                "this", "require", "import", "export", "class", "const", "let", "var",
                "throw", "try", "finally", "instanceof", "in", "of", "with", "default"}
_JS_DEF_PATTERNS = [
    (re.compile(r"\bfunction\s*\*?\s*([A-Za-z_$][\w$]*)\s*\("), "Function"),
    (re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*"
                r"(?:async\s+)?(?:function\b|\([^)]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>)"), "Function"),
    (re.compile(r"\bclass\s+([A-Za-z_$][\w$]*)"), "Class"),
    (re.compile(r"(?m)^[ \t]*(?:async\s+|static\s+|get\s+|set\s+)*([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{"), "Method"),
]
_CALL_RE = re.compile(r"([A-Za-z_$][\w$]*)\s*\(")


def parse_repo_spec(raw: str) -> Tuple[str, str, str]:
    """'owner/repo', a github URL, or 'owner/repo/tree/branch' -> (owner, repo, branch)."""
    s = str(raw or "").strip()
    s = s.replace("https://", "").replace("http://", "")
    s = s.replace("www.", "").replace("github.com/", "").rstrip("/")
    if s.endswith(".git"):
        s = s[:-4]
    parts = s.split("/")
    if len(parts) < 2:
        raise ValueError("expected owner/repo, got %r" % raw)
    branch = "/".join(parts[3:]) if len(parts) >= 4 and parts[2] == "tree" else ""  # keep slash branches (feature/x)
    return parts[0], parts[1], branch


def _gh(url: str, token: Optional[str], raw: bool = False):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "keystone-scan"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = _urequest.Request(url, headers=headers)
    with _urequest.urlopen(req, timeout=20) as r:     # nosec - fixed github hosts
        data = r.read()
    return data if raw else _json.loads(data.decode("utf-8"))


def fetch_github_python(owner: str, repo: str, branch: str = "",
                        token: Optional[str] = None) -> Dict[str, str]:
    """Fetch a public repo's source files (Python + JS/TS): {path: source}. Skips vendored and
    minified noise. Network; honest on rate limit. (Name kept for back-compat; multi-language.)"""
    if not branch:
        meta = _gh("https://api.github.com/repos/%s/%s" % (owner, repo), token)
        branch = meta.get("default_branch") or "main"
    tree = _gh("https://api.github.com/repos/%s/%s/git/trees/%s?recursive=1"
               % (owner, repo, branch), token)

    def _ok(p: str) -> bool:
        pl = p.lower()
        if any(s in pl for s in ("node_modules/", "/dist/", "/build/", "/vendor/", ".min.js", ".d.ts")):
            return False
        return os.path.splitext(pl)[1] in _SOURCE_EXT

    paths = [n["path"] for n in tree.get("tree", [])
             if n.get("type") == "blob" and _ok(str(n.get("path", "")))
             and int(n.get("size", 0) or 0) <= MAX_FILE_BYTES][:MAX_FILES]
    out: Dict[str, str] = {}
    for p in paths:
        try:
            src = _gh("https://raw.githubusercontent.com/%s/%s/%s/%s" % (owner, repo, branch, p),
                      token, raw=True).decode("utf-8", "replace")
            out[p] = src
        except Exception:
            continue
    return out


def _brace_body(src: str, from_idx: int) -> str:
    """The {...}-balanced block starting at the first '{' at/after from_idx (a JS function body)."""
    o = src.find("{", from_idx)
    if o < 0:
        return ""
    depth = 0
    for i in range(o, len(src)):
        c = src[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return src[o:i + 1]
    return src[o:]


def _py_collect(src: str, path: str, add) -> None:
    """Collect Python defs + their called names via ast (accurate)."""
    try:
        tree = ast.parse(src, filename=path)
    except (SyntaxError, ValueError):
        return

    def walk(node, prefix):
        for child in ast.iter_child_nodes(node):
            if type(child).__name__ in _DEF_TYPES:
                fqn = (prefix + "." + child.name) if prefix else (path + "::" + child.name)
                callees = set()
                for n in ast.walk(child):
                    if isinstance(n, ast.Call):
                        f = n.func
                        if isinstance(f, ast.Name):
                            callees.add(f.id)
                        elif isinstance(f, ast.Attribute):
                            callees.add(f.attr)
                add(child.name, fqn, path, _DEF_TYPES[type(child).__name__], child.lineno,
                    getattr(child, "end_lineno", child.lineno) or child.lineno, callees)
                walk(child, fqn)
    walk(tree, "")


def _js_collect(src: str, path: str, add) -> None:
    """Collect JS/TS defs + their called names via regex (name-based approximation)."""
    seen = set()
    for pat, dtype in _JS_DEF_PATTERNS:
        for m in pat.finditer(src):
            name = m.group(1)
            if name in _JS_KEYWORDS:
                continue
            start_line = src.count("\n", 0, m.start()) + 1
            key = (name, start_line)
            if key in seen:                      # don't double-count a def matched by two patterns
                continue
            seen.add(key)
            body = _brace_body(src, m.start())
            end_line = start_line + body.count("\n")
            callees = {c for c in _CALL_RE.findall(body) if c not in _JS_KEYWORDS and c != name}
            add(name, path + "::" + name, path, dtype, start_line, end_line, callees)


def _defs_and_edges(sources: Dict[str, str]):
    """Parse sources -> (definitions, edges). Python via ast; JS/TS via a name-based regex pass.
    Each def carries the names it calls; edges then resolve those names to def ids globally."""
    defs: List[dict] = []
    name_to_ids: Dict[str, List[int]] = {}
    nid = [0]

    def add(name, fqn, path, dtype, start, end, callees):
        nid[0] += 1
        defs.append({"id": nid[0], "name": name, "fqn": fqn, "file_path": path,
                     "definition_type": dtype, "start_line": int(start or 1),
                     "end_line": int(end or start or 1), "_callees": set(callees)})
        name_to_ids.setdefault(name, []).append(nid[0])

    for path, src in sources.items():
        ext = os.path.splitext(path)[1].lower()
        if ext == ".py":
            _py_collect(src, path, add)
        elif ext in _JS_EXT:
            _js_collect(src, path, add)

    edges: List[Tuple[int, int]] = []
    seen = set()
    for d in defs:
        for cn in d["_callees"]:
            for tid in name_to_ids.get(cn, []):
                if tid == d["id"]:
                    continue
                key = (d["id"], tid)
                if key not in seen:
                    seen.add(key)
                    edges.append(key)
    for d in defs:
        d.pop("_callees", None)
    return defs, edges


def build_graph_duckdb(sources: Dict[str, str], out_path: str, repo_label: str) -> str:
    """Write a DuckDB in the exact Orbit schema (gl_definition/gl_edge/gl_file/gl_directory/
    _orbit_manifest) from parsed sources, so the existing engine can query it unchanged."""
    import duckdb
    defs, edges = _defs_and_edges(sources)
    files = sorted(sources.keys())
    dirs = sorted({os.path.dirname(p) for p in files if os.path.dirname(p)})
    def _many(sql, rows):
        if rows:
            con.executemany(sql, rows)
    if os.path.exists(out_path):       # else CREATE TABLE crashes on a reused out_path (CatalogException)
        os.remove(out_path)
    con = duckdb.connect(out_path)
    con.execute("CREATE TABLE gl_directory (id BIGINT, path VARCHAR, name VARCHAR)")
    _many("INSERT INTO gl_directory VALUES (?, ?, ?)",
          [(i + 1, d, os.path.basename(d)) for i, d in enumerate(dirs)])
    con.execute("CREATE TABLE gl_file (id BIGINT, path VARCHAR, name VARCHAR, extension VARCHAR, language VARCHAR)")
    _many("INSERT INTO gl_file VALUES (?, ?, ?, ?, ?)",
          [(i + 1, p, os.path.basename(p), os.path.splitext(p)[1].lower(),
            _LANG.get(os.path.splitext(p)[1].lower(), "Python")) for i, p in enumerate(files)])
    con.execute("CREATE TABLE gl_definition (id BIGINT, name VARCHAR, fqn VARCHAR, file_path VARCHAR, "
                "definition_type VARCHAR, start_line BIGINT, end_line BIGINT)")
    _many("INSERT INTO gl_definition VALUES (?, ?, ?, ?, ?, ?, ?)",
          [(d["id"], d["name"], d["fqn"], d["file_path"], d["definition_type"],
            d["start_line"], d["end_line"]) for d in defs])
    con.execute("CREATE TABLE gl_edge (source_id BIGINT, source_kind VARCHAR, relationship_kind VARCHAR, "
                "target_id BIGINT, target_kind VARCHAR)")
    _many("INSERT INTO gl_edge VALUES (?, ?, ?, ?, ?)",
          [(s, "Definition", "CALLS", t, "Definition") for (s, t) in edges])
    con.execute("CREATE TABLE _orbit_manifest (repo_path VARCHAR, project_id BIGINT, parent_repo_path VARCHAR, "
                "branch VARCHAR, commit_sha VARCHAR, status VARCHAR, last_indexed_at VARCHAR, error_message VARCHAR)")
    con.execute("INSERT INTO _orbit_manifest VALUES (?, NULL, NULL, '', '', 'indexed', '', NULL)", [repo_label])
    con.close()
    return out_path


def scan_repo(spec: str, token: Optional[str] = None, out_dir: Optional[str] = None):
    """Fetch a public repo, build its Orbit-shaped graph on the fly, and return a
    (graph, stats) pair the gate can run on. Zero pre-indexing."""
    from core import graph as graph_mod
    owner, repo, branch = parse_repo_spec(spec)
    sources = fetch_github_python(owner, repo, branch, token)
    if not sources:
        raise RuntimeError("no Python files fetched for %s (private, empty, or rate-limited)" % spec)
    out_dir = out_dir or tempfile.mkdtemp(prefix="ks-scan-")
    path = os.path.join(out_dir, "scan.duckdb")
    label = "%s/%s" % (owner, repo)
    build_graph_duckdb(sources, path, label)
    g = graph_mod.Graph(path=path, mode="LIVE")
    return g, {"repo": label, "files": len(sources), "definitions": g.total_definitions()}
