#!/usr/bin/env bash
# Keystone — one-command local launcher (macOS / Linux).
#
#   ./run.sh
#
# Boots the FastAPI backend against the committed REAL Orbit self-index
# (data/keystone_self_graph.duckdb, 262 defs), in LIVE mode, with a live `orbit sql`
# cross-check when the orbit CLI is present and a real LLM review brief/agent when a
# free key is in .env. No paid services; degrades gracefully offline.
set -euo pipefail
cd "$(dirname "$0")"

echo "Keystone -> installing deps..."
python3 -m pip install --quiet -r requirements.txt

# Point the backend at the committed real Orbit index (same graph the public deploy uses).
export KEYSTONE_GRAPH_PATH="data/keystone_self_graph.duckdb"
export KEYSTONE_ORBIT_DB="data/keystone_self_graph.duckdb"
export KEYSTONE_PREFER_LIVE="1"

# Drive the Orbit CLI directly if installed (via glab), so the live `orbit sql`
# cross-check fires and the orbit-verified badge is a live query.
for c in "$HOME/.local/share/glab-cli/bin/orbit" "$(command -v orbit || true)"; do
  if [ -n "$c" ] && [ -x "$c" ]; then export KEYSTONE_ORBIT_BINARY="$c";
    echo "Orbit CLI found -> live orbit sql cross-check ENABLED"; break; fi
done

PORT=8787
echo "Keystone -> http://127.0.0.1:${PORT}  (Ctrl+C to stop)"
( sleep 1.5; (command -v open >/dev/null && open "http://127.0.0.1:${PORT}") || \
  (command -v xdg-open >/dev/null && xdg-open "http://127.0.0.1:${PORT}") || true ) &
exec python3 -m uvicorn backend.app:app --host 127.0.0.1 --port "${PORT}"
