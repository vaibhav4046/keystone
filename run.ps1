# Keystone — one-command local launcher (Windows / PowerShell).
#
#   ./run.ps1
#
# Boots the FastAPI backend against the committed REAL Orbit self-index
# (data/keystone_self_graph.duckdb, 262 defs), in LIVE mode, with a live `orbit sql`
# cross-check when the orbit CLI is present and a real LLM review brief/agent when a
# free key is in .env. No paid services; everything degrades gracefully offline.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Keystone -> installing deps..." -ForegroundColor Cyan
python -m pip install --quiet -r requirements.txt

# Point the backend at the committed real Orbit index (same graph the public deploy uses).
$env:KEYSTONE_GRAPH_PATH = "data\keystone_self_graph.duckdb"
$env:KEYSTONE_ORBIT_DB   = "data\keystone_self_graph.duckdb"
$env:KEYSTONE_PREFER_LIVE = "1"

# If the Orbit CLI (installed via glab) is present, drive it directly so the live
# `orbit sql` cross-check fires (the orbit-verified badge becomes a live query).
$orbit = Join-Path $env:LOCALAPPDATA "glab-cli\bin\orbit.exe"
if (Test-Path $orbit) {
  $env:KEYSTONE_ORBIT_BINARY = $orbit
  Write-Host "Orbit CLI found -> live orbit sql cross-check ENABLED" -ForegroundColor Green
} else {
  Write-Host "Orbit CLI not found -> using the committed DuckDB index (cross-check shows recorded)" -ForegroundColor Yellow
}

$port = 8787
Write-Host "Keystone -> http://127.0.0.1:$port  (Ctrl+C to stop)" -ForegroundColor Cyan
Start-Process "http://127.0.0.1:$port"
python -m uvicorn backend.app:app --host 127.0.0.1 --port $port
