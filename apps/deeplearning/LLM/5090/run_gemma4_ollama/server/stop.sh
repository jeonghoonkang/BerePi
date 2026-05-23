#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="${APP_DIR}/server.pid"
OLLAMA_PID_FILE="${APP_DIR}/ollama.pid"

if [[ ! -f "${PID_FILE}" ]]; then
  echo "No PID file found."
  exit 0
fi

PID="$(cat "${PID_FILE}")"
if kill -0 "${PID}" 2>/dev/null; then
  kill "${PID}"
  echo "Stopped Gemma4 service PID ${PID}"
else
  echo "Process ${PID} is not running."
fi
rm -f "${PID_FILE}"

if [[ -f "${OLLAMA_PID_FILE}" ]]; then
  OLLAMA_PID="$(cat "${OLLAMA_PID_FILE}")"
  if kill -0 "${OLLAMA_PID}" 2>/dev/null; then
    kill "${OLLAMA_PID}"
    echo "Stopped Ollama PID ${OLLAMA_PID}"
  fi
  rm -f "${OLLAMA_PID_FILE}"
fi
