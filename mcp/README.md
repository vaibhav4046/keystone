# Keystone MCP server

One Model Context Protocol (MCP) server that exposes the Keystone merge gate to **any
MCP-compatible client** - Claude Code, Codex, Cursor, Claude Desktop, Hermes, OpenClaw,
Odysseus, and anything else that speaks MCP. The agent calls a tool, the GitLab Orbit
graph answers with a deterministic **ALLOW / HOLD / BLOCK** verdict. No LLM on the verdict.

## Tools exposed

| Tool | What it does |
|------|--------------|
| `gate_symbol(symbol, graph_path?)` | Blast radius + ALLOW/HOLD/BLOCK for one changed symbol. |
| `gate_diff(unified_diff, graph_path?)` | Extracts changed symbols from a diff and returns a per-symbol + overall verdict. |
| `cross_mr_collision(symbols_a, symbols_b, graph_path?)` | Do two MRs share runtime dependents that break together (no Git conflict)? Returns the collision packet + safe merge order. |
| `scan_repo_and_gate(repo, github_token?, top?)` | Builds the Orbit graph for ANY public repo on the fly (zero pre-indexing) and gates its highest-blast symbols. |

`graph_path` defaults to Keystone's bundled self-index (`data/keystone_self_graph.duckdb`);
point it at any Orbit DuckDB graph.

## Install

```
pip install -r mcp/requirements.txt      # adds the MCP SDK; engine uses the root requirements
python mcp/keystone_server.py --selftest  # sanity check, no client needed
```

The server speaks MCP over **stdio**: clients launch `python mcp/keystone_server.py`.

## Configure it in your client

Every MCP client uses the same shape - a `command` + `args` that launch the stdio server.
Replace `/ABS/PATH` with the absolute path to this repo.

### Claude Code

```
claude mcp add keystone -- python /ABS/PATH/keystone/mcp/keystone_server.py
```

or commit a project-scoped `.mcp.json` so the whole team gets it:

```json
{
  "mcpServers": {
    "keystone": {
      "command": "python",
      "args": ["/ABS/PATH/keystone/mcp/keystone_server.py"]
    }
  }
}
```

### Claude Desktop / Codex / Cursor / generic MCP clients

Add the same block to the client's MCP config file (Claude Desktop:
`claude_desktop_config.json`; Cursor: `.cursor/mcp.json`; Codex and others: their
`mcpServers` config):

```json
{
  "mcpServers": {
    "keystone": {
      "command": "python",
      "args": ["/ABS/PATH/keystone/mcp/keystone_server.py"]
    }
  }
}
```

### Hermes / OpenClaw / Odysseus / any other harness

If the harness supports MCP stdio servers (most agent harnesses now do), use the **same**
block above - point `command`/`args` at `keystone_server.py`. If the harness wraps MCP
differently, it still ultimately launches a stdio command; give it:

```
command: python
args:    ["/ABS/PATH/keystone/mcp/keystone_server.py"]
```

On Windows, use the absolute `python.exe` (or `py`) and forward slashes, e.g.
`"command": "python", "args": ["D:/project/keystone/mcp/keystone_server.py"]`.

## Continuity server - carry your context across tools

A second server (`mcp/continuity_server.py`) holds your running summary, memories, and open
todos on disk, so when one tool's context runs out you switch tools, connect the same
server, call `get_handoff`, and continue exactly where you left off.

| Tool | What it does |
|------|--------------|
| `get_handoff()` | The continue-here call: returns summary + all memories + open todos as a ready-to-paste block. Call first when you switch tools. |
| `set_summary(text)` | Set the one-paragraph "where things stand" summary. |
| `save_memory(title, body, type?)` | Save/update a durable fact or decision (dedup by title). |
| `recall(query?)` | All memories, or those matching a query. |
| `add_todo(text)` / `complete_todo(id)` | Track next steps. |

Storage is one JSON file at `KEYSTONE_CONTEXT_STORE` (default `mcp/continuity_store.json`),
so the state is portable and survives across tools and runs. Verified with
`python mcp/continuity_server.py --selftest`.

Register it alongside the gate server (same shape, different command):

```json
{
  "mcpServers": {
    "keystone-continuity": {
      "command": "python",
      "args": ["/ABS/PATH/keystone/mcp/continuity_server.py"]
    }
  }
}
```

Typical flow: in the tool you are leaving, call `set_summary` + `save_memory` + `add_todo`.
In the new tool (Codex, ChatGPT, Claude Code, Odysseus, ...), call `get_handoff` and keep going.

## Why this matters

The gate stops being a Keystone-only website and becomes a control any agent, in any
harness, can call before it merges. Same deterministic engine, no LLM, available
everywhere through one open protocol. And with the continuity server, your working context
travels with you between tools instead of dying when one runs out.
