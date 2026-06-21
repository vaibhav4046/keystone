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
import tempfile
import urllib.request as _urequest
from typing import Dict, List, Optional, Tuple

MAX_FILES = 400
MAX_FILE_BYTES = 300_000
# Match the capitalized Orbit vocabulary the graph filters on (core/graph.py CALLABLE_TYPES);
# lowercase values silently miss every WHERE definition_type IN (...) query on a scanned graph.
_DEF_TYPES = {"FunctionDef": "Function", "AsyncFunctionDef": "Function", "ClassDef": "Class"}


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
    """Fetch a public repo's Python files: {path: source}. Network; honest on rate limit."""
    if not branch:
        meta = _gh("https://api.github.com/repos/%s/%s" % (owner, repo), token)
        branch = meta.get("default_branch") or "main"
    tree = _gh("https://api.github.com/repos/%s/%s/git/trees/%s?recursive=1"
               % (owner, repo, branch), token)
    paths = [n["path"] for n in tree.get("tree", [])
             if n.get("type") == "blob" and str(n.get("path", "")).endswith(".py")
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


def _defs_and_edges(sources: Dict[str, str]):
    """ast-parse sources -> (definitions, edges). Two passes: collect defs, then resolve
    each def's Call names to a def id (name-based)."""
    defs: List[dict] = []
    name_to_ids: Dict[str, List[int]] = {}
    nid = [0]

    def _walk_defs(node, path, prefix):
        for child in ast.iter_child_nodes(node):
            kind = type(child).__name__
            if kind in _DEF_TYPES:
                nid[0] += 1
                did = nid[0]
                fqn = (prefix + "." + child.name) if prefix else (path + "::" + child.name)
                defs.append({"id": did, "name": child.name, "fqn": fqn, "file_path": path,
                             "definition_type": _DEF_TYPES[kind],
                             "start_line": child.lineno,
                             "end_line": getattr(child, "end_lineno", child.lineno) or child.lineno,
                             "_node": child})
                name_to_ids.setdefault(child.name, []).append(did)
                _walk_defs(child, path, fqn)

    for path, src in sources.items():
        try:
            tree = ast.parse(src, filename=path)
        except (SyntaxError, ValueError):
            continue
        _walk_defs(tree, path, "")

    edges: List[Tuple[int, int]] = []
    seen = set()
    for d in defs:
        callee_names = set()
        for n in ast.walk(d["_node"]):
            if isinstance(n, ast.Call):
                f = n.func
                if isinstance(f, ast.Name):
                    callee_names.add(f.id)
                elif isinstance(f, ast.Attribute):
                    callee_names.add(f.attr)
        for cn in callee_names:
            for tid in name_to_ids.get(cn, []):
                if tid == d["id"]:
                    continue
                key = (d["id"], tid)
                if key not in seen:
                    seen.add(key)
                    edges.append(key)
    for d in defs:
        d.pop("_node", None)
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
          [(i + 1, p, os.path.basename(p), ".py", "Python") for i, p in enumerate(files)])
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
