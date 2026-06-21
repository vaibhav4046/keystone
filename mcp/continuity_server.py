"""Keystone Continuity MCP server.

A portable working-memory server. Connect it in any MCP client - Claude Code, Codex,
ChatGPT, Cursor, Hermes, OpenClaw, Odysseus - and it carries your running summary,
memories, and open todos on disk. When one tool's context runs out, switch tools, point
them at this same server, call `get_handoff`, and continue exactly where you left off.

Storage is a single JSON file (KEYSTONE_CONTEXT_STORE env var, else
mcp/continuity_store.json), so the state is portable and survives across tools and runs.

Run as a stdio MCP server:
    python mcp/continuity_server.py

Self-test (round-trip persistence, no MCP client needed):
    python mcp/continuity_server.py --selftest
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

_DEFAULT_STORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "continuity_store.json")


def _store_path() -> str:
    return os.environ.get("KEYSTONE_CONTEXT_STORE", _DEFAULT_STORE)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty() -> dict:
    return {"summary": "", "updated_at": None, "memories": [], "todos": []}


def _load() -> dict:
    path = _store_path()
    if not os.path.exists(path):
        return _empty()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return _empty()
    base = _empty()
    base.update({k: data.get(k, base[k]) for k in base})
    return base


def _save(data: dict) -> None:
    data["updated_at"] = _now()
    path = _store_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, path)            # atomic


def _next_id(items: list) -> int:
    return (max([int(i.get("id", 0)) for i in items], default=0) + 1)


mcp = FastMCP("keystone-continuity")


def set_summary(summary: str) -> dict:
    """Set the rolling handoff summary - the one paragraph a fresh agent reads first to
    understand where the work stands. Overwrites the previous summary.
    """
    data = _load()
    data["summary"] = summary
    _save(data)
    return {"ok": True, "summary": summary, "updated_at": data["updated_at"]}


def save_memory(title: str, body: str, type: str = "note") -> dict:
    """Save a memory (a durable fact, decision, or piece of context). If a memory with the
    same title exists it is updated in place, otherwise a new one is appended.
    type is a free label, e.g. decision / fact / project / reference / todo-context.
    """
    data = _load()
    for m in data["memories"]:
        if m.get("title") == title:
            m.update({"body": body, "type": type, "ts": _now()})
            _save(data)
            return {"ok": True, "updated": True, "id": m["id"], "title": title}
    mem = {"id": _next_id(data["memories"]), "title": title, "body": body,
           "type": type, "ts": _now()}
    data["memories"].append(mem)
    _save(data)
    return {"ok": True, "updated": False, "id": mem["id"], "title": title}


def recall(query: str = "") -> dict:
    """Return memories. With no query, returns all. With a query, returns memories whose
    title or body contains it (case-insensitive). Use this to pull back relevant context.
    """
    data = _load()
    mems = data["memories"]
    if query:
        q = query.lower()
        mems = [m for m in mems if q in (m.get("title", "") + " " + m.get("body", "")).lower()]
    return {"ok": True, "count": len(mems), "memories": mems}


def add_todo(text: str) -> dict:
    """Add an open todo / next-step so the next tool knows what to do next."""
    data = _load()
    todo = {"id": _next_id(data["todos"]), "text": text, "done": False, "ts": _now()}
    data["todos"].append(todo)
    _save(data)
    return {"ok": True, "id": todo["id"], "text": text}


def complete_todo(todo_id: int) -> dict:
    """Mark a todo done by id."""
    data = _load()
    for t in data["todos"]:
        if int(t.get("id", -1)) == int(todo_id):
            t["done"] = True
            _save(data)
            return {"ok": True, "id": todo_id, "done": True}
    return {"ok": False, "error": "not_found", "id": todo_id}


def get_handoff() -> dict:
    """THE continue-here call. Returns the full working context to feed a fresh agent in a
    new tool: the summary, every memory, and the open todos - plus a ready-to-paste text
    block. Call this first when you switch tools.
    """
    data = _load()
    open_todos = [t for t in data["todos"] if not t.get("done")]
    lines = ["# Handoff context (Keystone Continuity)"]
    if data.get("updated_at"):
        lines.append("_updated: %s_" % data["updated_at"])
    lines.append("\n## Summary\n" + (data.get("summary") or "(none set)"))
    if data["memories"]:
        lines.append("\n## Memories")
        for m in data["memories"]:
            lines.append("- [%s] %s: %s" % (m.get("type", "note"), m.get("title", ""), m.get("body", "")))
    if open_todos:
        lines.append("\n## Open todos")
        for t in open_todos:
            lines.append("- (#%s) %s" % (t.get("id"), t.get("text", "")))
    return {"ok": True, "summary": data.get("summary", ""), "memories": data["memories"],
            "open_todos": open_todos, "updated_at": data.get("updated_at"),
            "handoff_text": "\n".join(lines)}


def seed_from_memory(memory_dir: str = "") -> dict:
    """Auto-seed the store from an existing MEMORY.md index (the Claude file-memory format:
    lines like '- [Title](file.md) - hook'). Each entry becomes a memory; when the linked
    file exists its frontmatter type and body are pulled in too. Dedupes by title, so it is
    safe to re-run. memory_dir defaults to the KEYSTONE_MEMORY_DIR env var.
    """
    mdir = memory_dir or os.environ.get("KEYSTONE_MEMORY_DIR", "")
    if not mdir:
        return {"ok": False, "error": "no_memory_dir", "hint": "Pass memory_dir or set KEYSTONE_MEMORY_DIR."}
    index = os.path.join(mdir, "MEMORY.md")
    if not os.path.exists(index):
        return {"ok": False, "error": "no_MEMORY.md", "path": index}
    with open(index, "r", encoding="utf-8") as fh:
        text = fh.read()
    rows = re.findall(r"^-\s*\[([^\]]+)\]\(([^)]+)\)\s*[—\-]\s*(.*)$", text, re.M)
    data = _load()
    imported = 0
    for title, fname, hook in rows:
        title = title.strip()
        body = hook.strip()
        mtype = "reference"
        fpath = os.path.join(mdir, fname.strip())
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as fh:
                    raw = fh.read()
                mt = re.search(r"type:\s*([A-Za-z|/ ]+)", raw)
                if mt:
                    mtype = mt.group(1).split("|")[0].strip()
                bodytext = re.sub(r"^---.*?---\s*", "", raw, count=1, flags=re.S).strip()
                if bodytext:
                    body = (hook.strip() + "\n\n" + bodytext) if hook.strip() else bodytext
            except Exception:
                pass
        body = body[:4000]
        existing = next((m for m in data["memories"] if m.get("title") == title), None)
        if existing:
            existing.update({"body": body, "type": mtype, "ts": _now()})
        else:
            data["memories"].append({"id": _next_id(data["memories"]), "title": title,
                                     "body": body, "type": mtype, "ts": _now()})
        imported += 1
    if not data.get("summary"):
        data["summary"] = ("Seeded %d memories from MEMORY.md. Latest project context "
                           "imported for cross-tool handoff." % imported)
    _save(data)
    return {"ok": True, "imported": imported, "source": index, "store": _store_path()}


for _fn in (set_summary, save_memory, recall, add_todo, complete_todo, get_handoff, seed_from_memory):
    mcp.tool()(_fn)


def _selftest() -> int:
    import tempfile
    os.environ["KEYSTONE_CONTEXT_STORE"] = os.path.join(tempfile.mkdtemp(), "store.json")
    set_summary("Mid-refactor of the auth module; switching from Codex to Claude.")
    save_memory("auth-decision", "Use HttpOnly cookie sessions, not localStorage tokens.", "decision")
    save_memory("auth-decision", "Use HttpOnly cookie sessions; SameSite=None for cross-site.", "decision")  # update
    add_todo("Finish the /api/refresh endpoint")
    add_todo("Add tests for token rotation")
    complete_todo(1)
    # reload from disk to prove persistence
    h = get_handoff()
    assert h["summary"].startswith("Mid-refactor"), h["summary"]
    assert len(h["memories"]) == 1, "title update should not duplicate"
    assert h["memories"][0]["body"].endswith("cross-site."), "memory not updated"
    assert len(h["open_todos"]) == 1 and h["open_todos"][0]["id"] == 2, h["open_todos"]
    r = recall("cookie")
    assert r["count"] == 1, r
    print("SELFTEST OK - store:", _store_path())
    print(h["handoff_text"])
    return 0


if __name__ == "__main__":
    if "--seed" in sys.argv:
        _i = sys.argv.index("--seed")
        _md = sys.argv[_i + 1] if len(sys.argv) > _i + 1 else ""
        print(json.dumps(seed_from_memory(_md), indent=2))
        raise SystemExit(0)
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    mcp.run()
