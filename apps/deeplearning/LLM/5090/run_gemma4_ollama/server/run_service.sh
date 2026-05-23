#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${APP_DIR}/logs"
mkdir -p "${LOG_DIR}"

export OLLAMA_MODEL="${OLLAMA_MODEL:-gemma4}"
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
export GEMMA4_SERVER_HOST="${GEMMA4_SERVER_HOST:-0.0.0.0}"
export GEMMA4_SERVER_PORT="${GEMMA4_SERVER_PORT:-8082}"
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
export OLLAMA_PID_FILE="${OLLAMA_PID_FILE:-${APP_DIR}/ollama.pid}"
OLLAMA_BIN="${OLLAMA_BIN:-$(command -v ollama || echo /usr/local/bin/ollama)}"

OLLAMA_PID=""

cleanup() {
  if [[ -n "${OLLAMA_PID}" ]] && kill -0 "${OLLAMA_PID}" 2>/dev/null; then
    kill "${OLLAMA_PID}" 2>/dev/null || true
  fi
  rm -f "${OLLAMA_PID_FILE}"
}
trap cleanup EXIT

if ! curl -fsS --max-time 2 "${OLLAMA_BASE_URL}/api/tags" >/dev/null 2>&1; then
  "${OLLAMA_BIN}" serve >> "${LOG_DIR}/ollama.log" 2>&1 &
  OLLAMA_PID="$!"
  echo "${OLLAMA_PID}" > "${OLLAMA_PID_FILE}"
fi

for _ in {1..30}; do
  if curl -fsS --max-time 2 "${OLLAMA_BASE_URL}/api/tags" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if [[ "${AUTO_PULL:-1}" == "1" ]]; then
  "${OLLAMA_BIN}" pull "${OLLAMA_MODEL}"
fi

exec python3 "${APP_DIR}/server.py"
