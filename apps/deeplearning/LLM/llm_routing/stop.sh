#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="${APP_DIR}/server.pid"

if [[ ! -f "${PID_FILE}" ]]; then
  echo "LLM Routing is not running."
  exit 0
fi

PID="$(cat "${PID_FILE}")"
if kill -0 "${PID}" 2>/dev/null; then
  kill "${PID}"
  for _ in {1..10}; do
    if ! kill -0 "${PID}" 2>/dev/null; then
      break
    fi
    sleep 1
  done
fi
rm -f "${PID_FILE}"
echo "LLM Routing stopped."
