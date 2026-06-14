"""Capture a REAL LLM tool-using agent run for the public bundle.

The static public deploy has no backend, so a remote judge cannot trigger the live
agent. This records one genuine multi-step run of core/agent.run_agent (the model
autonomously calling the deterministic engine tools) on the committed self-graph for
the headline symbols, and writes web/assistant_sample.json. build_static.py embeds it
so the ASSISTANT panel shows a real recorded agent trace (provider-named) even on the
static deploy, while the LIVE backend serves fresh runs for any symbol.

The recorded text is non-deterministic (it is a real model output), so it is committed
as a static artifact and read verbatim by the build — CI rebuilds web/data.json
byte-identically without any network or key. Run this only to refresh the sample:

    python scripts/capture_assistant_sample.py
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

DATA = os.path.join(ROOT, "data")
WEB = os.path.join(ROOT, "web")
SELF_GRAPH = os.path.join(DATA, "keystone_self_graph.duckdb")
OUT = os.path.join(WEB, "assistant_sample.json")

# headline symbols to record (must exist on the self-graph); first is the demo default
SYMBOLS = ["compute_blast_radius", "append"]


def main() -> int:
    os.environ["KEYSTONE_LEDGER_KEY"] = "keystone-public-sample-v1"
    import core.audit as _audit
    _audit._CACHED_KEY = None
    from core import (graph as graph_mod, impact as impact_mod, seed as seed_mod,
                      agent as agent_mod, llm as llm_mod)
    from core.audit import Ledger

    if not os.path.exists(SELF_GRAPH):
        print(f"missing {SELF_GRAPH}", file=sys.stderr)
        return 2
    providers = llm_mod.available_providers()
    if not providers:
        print("no LLM provider keys configured; cannot record a real agent run", file=sys.stderr)
        return 2

    g = graph_mod.Graph(path=SELF_GRAPH, mode="LIVE")
    # rebuild the SAME seeded ledger the static build uses, so the recorded facts match
    import tempfile
    lp = os.path.join(tempfile.mkdtemp(), "assistant_seed.jsonl")
    led = Ledger(lp)
    for row in seed_mod.seed_rows_for(g):
        sig = impact_mod.blast_radius_signature(row["blast_radius_set"], row.get("epicenter_id"))
        led.append(actor=row["actor"], change_id=row["change_id"], target_symbols=row["target_symbols"],
                   blast_radius_set=row["blast_radius_set"], signature=sig,
                   decision=row["decision"], rationale=row["rationale"], extra={"seeded": True})

    out = {}
    for sym in SYMBOLS:
        if impact_mod.compute_blast_radius(g, sym) is None:
            print(f"  skip {sym}: not on graph", file=sys.stderr)
            continue
        res = agent_mod.run_agent(g, led, sym, "Is it safe to approve? What should I do and who should review?")
        out[sym] = res
        tag = ("REAL " + str(res.get("provider"))) if not res.get("deterministic") else "deterministic"
        print(f"  {sym}: {tag}, {len(res.get('steps', []))} tool steps")
    g.close()

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, sort_keys=True)
    print(f"wrote {OUT} ({len(out)} symbols; providers={providers})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
