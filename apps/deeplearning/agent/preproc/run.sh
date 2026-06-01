#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

exec streamlit run app.py --server.address 0.0.0.0 --server.port "${STREAMLIT_PORT:-2281}"
