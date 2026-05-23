#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${APP_DIR}/logs"
PID_FILE="${APP_DIR}/server.pid"
OLLAMA_PID_FILE="${APP_DIR}/ollama.pid"
mkdir -p "${LOG_DIR}"

export OLLAMA_MODEL="${OLLAMA_MODEL:-gemma4}"
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
export GEMMA4_SERVER_HOST="${GEMMA4_SERVER_HOST:-0.0.0.0}"
export GEMMA4_SERVER_PORT="${GEMMA4_SERVER_PORT:-8082}"
export OLLAMA_PID_FILE
export AUTO_PULL="${AUTO_PULL:-1}"
OLLAMA_BIN="${OLLAMA_BIN:-$(command -v ollama || echo /usr/local/bin/ollama)}"

if [[ -f "${PID_FILE}" ]] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
  echo "Gemma4 service is already running with PID $(cat "${PID_FILE}")"
  exit 0
fi

if ! curl -fsS --max-time 2 "${OLLAMA_BASE_URL}/api/tags" >/dev/null 2>&1; then
  nohup "${OLLAMA_BIN}" serve > "${LOG_DIR}/ollama.log" 2>&1 &
  echo "$!" > "${OLLAMA_PID_FILE}"
fi

for _ in {1..30}; do
  if curl -fsS --max-time 2 "${OLLAMA_BASE_URL}/api/tags" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if [[ "${AUTO_PULL}" == "1" ]]; then
  "${OLLAMA_BIN}" pull "${OLLAMA_MODEL}"
fi

nohup python3 "${APP_DIR}/server.py" > "${LOG_DIR}/server.log" 2>&1 &
echo "$!" > "${PID_FILE}"
echo "Started Gemma4 service with PID $(cat "${PID_FILE}")"
echo "Open http://localhost:8082"
