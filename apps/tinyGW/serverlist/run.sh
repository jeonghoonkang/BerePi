#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

HOST="${SERVERLIST_HOST:-0.0.0.0}"
PORT="${SERVERLIST_PORT:-2298}"
PYTHON_BIN="${PYTHON:-python3}"

if command -v streamlit >/dev/null 2>&1; then
  exec streamlit run app.py --server.address "$HOST" --server.port "$PORT"
fi

if "$PYTHON_BIN" -m streamlit --version >/dev/null 2>&1; then
  exec "$PYTHON_BIN" -m streamlit run app.py --server.address "$HOST" --server.port "$PORT"
fi

echo "Streamlit is not installed or not available in PATH." >&2
echo "Install dependencies first: pip install -r requirements.txt" >&2
exit 1
