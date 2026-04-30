#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

exec streamlit run human_detect.py --server.address 0.0.0.0 --server.port 2290
