#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${APP_DIR}/logs"
PID_FILE="${APP_DIR}/server.pid"
mkdir -p "${LOG_DIR}"

export LLM_ROUTING_HOST="${LLM_ROUTING_HOST:-0.0.0.0}"
export LLM_ROUTING_PORT="${LLM_ROUTING_PORT:-4004}"

if [[ -f "${PID_FILE}" ]] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
  echo "LLM Routing is already running with PID $(cat "${PID_FILE}")"
  exit 0
fi
rm -f "${PID_FILE}"

if python3 - "${LLM_ROUTING_PORT}" <<'PY'
import socket
import sys

port = int(sys.argv[1])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.settimeout(1)
    raise SystemExit(0 if sock.connect_ex(("127.0.0.1", port)) == 0 else 1)
PY
then
  echo "Port ${LLM_ROUTING_PORT} is already in use." >&2
  exit 1
fi

cd "${APP_DIR}"
nohup python3 server.py --host "${LLM_ROUTING_HOST}" --port "${LLM_ROUTING_PORT}" > "${LOG_DIR}/server.log" 2>&1 &
echo "$!" > "${PID_FILE}"
echo "LLM Routing started at http://127.0.0.1:${LLM_ROUTING_PORT} with PID $(cat "${PID_FILE}")"
