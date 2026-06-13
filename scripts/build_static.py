"""Precompute a static data bundle so the web hero deploys with NO backend.

Runs the deterministic engine over the fixture graph for every definition and
writes web/data.json: status, definitions, per-symbol impact and precedent, and
the seeded audit ledger. The frontend tries the live API first and falls back to
this bundle when no backend is reachable (a cold-clicked public deploy), labeled
FALLBACK. The authentic live local-graph run is shown in the demo video.
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import fixtures, graph as graph_mod, impact as impact_mod, orbit_cli
from core.audit import Ledger

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
WEB = os.path.join(ROOT, "web")
FIXTURE = os.path.join(DATA, "fixture_graph.duckdb")
LEDGER = os.path.join(DATA, "audit_ledger.jsonl")
ORBIT_SAMPLE = os.path.join(WEB, "orbit_sample_transcript.json")


def _sanitize_transcript(entries):
    """Redact the absolute binary path (no machine username in the public bundle)
    and drop volatile fields (duration_ms, ts) so the committed bundle is
    deterministic and a CI drift check can compare it byte-for-byte."""
    out = []
    for e in entries or []:
        cmd = e.get("command", "") or ""
        cmd = re.sub(r"^\S*orbit(?:\.exe)?'?", "orbit", cmd)  # first token -> 'orbit'
        out.append({
            "subcommand": e.get("subcommand"),
            "command": cmd,
            "ok": e.get("ok"),
            "stdout": (e.get("stdout") or "")[:600],
        })
    return out


def _orbit_transcript():
    """A real `orbit schema` + `orbit sql` transcript for the FALLBACK status panel,
    so a remote judge on the public deploy still sees evidence that the product
    drives Orbit's own CLI. Captured live when the orbit binary is available
    (and saved, sanitized, as the committed sample); otherwise the sample is reused."""
    if orbit_cli.cli_available():
        try:
            orbit_cli.clear_transcript()
            orbit_cli.schema()
            orbit_cli.probe()
            t = _sanitize_transcript(orbit_cli.get_transcript())
            if t:
                with open(ORBIT_SAMPLE, "w", encoding="utf-8") as f:
                    json.dump(t, f, indent=2)
                return t
        except Exception:
            pass
    if os.path.exists(ORBIT_SAMPLE):
        try:
            with open(ORBIT_SAMPLE, encoding="utf-8") as f:
                return _sanitize_transcript(json.load(f))
        except Exception:
            return []
    return []


def main():
    # The PUBLIC sample bundle uses a fixed, non-secret HMAC key so the committed
    # web/data.json is byte-identical on every machine (CI drift check) — the sample
    # is a build-time artifact labeled "verified at build time" in the UI, not a real
    # audit trail. Real deployments use a secret per-machine key (see core/audit.py).
    os.environ["KEYSTONE_LEDGER_KEY"] = "keystone-public-sample-v1"
    import core.audit as _audit
    _audit._CACHED_KEY = None  # force re-read with the fixed sample key

    fixtures.build_fixture_duckdb(FIXTURE)
    # fresh seeded ledger
    if os.path.exists(LEDGER):
        os.remove(LEDGER)
    led = Ledger(LEDGER)
    for row in fixtures.seed_ledger_rows():
        sig = impact_mod.blast_radius_signature(row["blast_radius_set"], row.get("epicenter_id"))
        led.append(actor=row["actor"], change_id=row["change_id"], target_symbols=row["target_symbols"],
                   blast_radius_set=row["blast_radius_set"], signature=sig,
                   decision=row["decision"], rationale=row["rationale"])

    g = graph_mod.Graph(prefer_live=False)
    names = g.all_definition_names()
    rep = g.schema_report()
    tx = _orbit_transcript()
    cli_ran = any(e.get("ok") for e in tx)
    bundle = {
        "static": True,
        "status": {
            "source_mode": "FALLBACK",
            # honest: the public deploy reads the committed fixture, but a REAL orbit
            # CLI run is recorded in the transcript below (captured on the live graph)
            "orbit_access": "CLI-recorded + DuckDB-fixture" if cli_ran else "DuckDB-fixture",
            "duckdb_path": "data/fixture_graph.duckdb (committed sample)",
            "tables": rep["tables"],
            "audit_chain": led.verify(),
            "definitions": g.total_definitions(),
            "integrity": {"hmac": True, "approve_token_required": False},
            # a real captured `orbit schema` + `orbit sql` transcript (recorded), so the
            # public FALLBACK deploy still shows the product driving Orbit's own CLI
            "orbit_cli_transcript": tx,
            "orbit_cli_recorded": cli_ran,
        },
        "definitions": names,
        "impact": {},
        "precedent": {},
        "audit": {"rows": led.rows(), "verify": led.verify()},
    }
    for n in names:
        imp = impact_mod.compute_blast_radius(g, n)
        if imp:
            bundle["impact"][n] = imp.to_dict()
            bundle["precedent"][n] = led.precedent(target_symbols=[n], signature=imp.signature)
    g.close()

    out = os.path.join(WEB, "data.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(bundle, f, separators=(",", ":"))
    print(f"wrote {out}  ({len(names)} symbols, {os.path.getsize(out)} bytes)")


if __name__ == "__main__":
    main()
