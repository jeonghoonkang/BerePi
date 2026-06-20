#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export LLM_ROUTING_HOST="${LLM_ROUTING_HOST:-0.0.0.0}"
export LLM_ROUTING_PORT="${LLM_ROUTING_PORT:-4004}"

cd "${APP_DIR}"
exec python3 server.py --host "${LLM_ROUTING_HOST}" --port "${LLM_ROUTING_PORT}"
