#!/usr/bin/env bash
set -euo pipefail

# Always run from the repo root (dart-agent)
cd "$(dirname "$0")"

# Load local environment overrides if present
if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

PYTHONPATH="${PYTHONPATH:-.}"
CHAINLIT_PORT="${CHAINLIT_PORT:-8500}"
CHAINLIT_HOST="${CHAINLIT_HOST:-0.0.0.0}"

echo "Starting MCP + Vendor servers..."
python3 -m src.servers.startup &
SERVERS_PID=$!

cleanup() {
  echo "Stopping MCP/Vendor servers..."
  kill "$SERVERS_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting Chainlit on ${CHAINLIT_HOST}:${CHAINLIT_PORT}..."
PYTHONPATH="$PYTHONPATH" chainlit run src/app.py -w --host "$CHAINLIT_HOST" --port "$CHAINLIT_PORT"
