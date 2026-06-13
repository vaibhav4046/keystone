"""Explicitly capture a real `glab orbit local` CLI transcript into the committed
web/orbit_sample_transcript.json, used by the public FALLBACK status panel.

This is deliberately SEPARATE from build_static.py: build_static must be
deterministic on any machine (the CI drift check compares the committed
web/data.json to a fresh build), so it never captures live. Run this only when you
want to refresh the recorded transcript, on a machine with the Orbit Local CLI:

    set KEYSTONE_ORBIT_BINARY=%LOCALAPPDATA%\\glab-cli\\bin\\orbit.exe   (Windows)
    python scripts/capture_orbit_transcript.py

The command label is normalized to the documented `glab orbit local <sub>` form
(the orbit binary is exactly what `glab orbit local` launches), the absolute path
is redacted, and volatile fields (duration, timestamp) are dropped so the sample is
stable. stdout is truncated. No secrets are captured.
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import orbit_cli

WEB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web"))
ORBIT_SAMPLE = os.path.join(WEB, "orbit_sample_transcript.json")


def _normalize(entries):
    out = []
    for e in entries or []:
        # rewrite "<abs>/orbit[.exe] <sub> ..." to the documented "glab orbit local <sub> ..."
        cmd = e.get("command", "") or ""
        cmd = re.sub(r"^\S*orbit(?:\.exe)?'?\s*", "glab orbit local ", cmd)
        out.append({
            "subcommand": e.get("subcommand"),
            "command": cmd,
            "ok": e.get("ok"),
            "stdout": (e.get("stdout") or "")[:600],
        })
    return out


def main():
    if not orbit_cli.cli_available():
        print("orbit CLI not available; set KEYSTONE_ORBIT_BINARY to the orbit binary. "
              "Leaving the committed sample unchanged.")
        return 1
    orbit_cli.clear_transcript()
    orbit_cli.schema()
    orbit_cli.probe()
    t = _normalize(orbit_cli.get_transcript())
    if not any(e["ok"] for e in t):
        print("no successful orbit invocation captured; leaving the committed sample unchanged.")
        return 1
    with open(ORBIT_SAMPLE, "w", encoding="utf-8") as f:
        json.dump(t, f, indent=2)
    print(f"wrote {ORBIT_SAMPLE} ({len(t)} entries). Now run scripts/build_static.py and commit both.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
