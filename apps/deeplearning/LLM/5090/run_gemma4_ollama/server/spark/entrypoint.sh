#!/usr/bin/env bash
set -euo pipefail

mkdir -p /app/state /app/logs /app/workspace /app/mach_stats

if [[ ! -f "${API_KEY_CONF_FILE:-/app/state/api_key.conf}" ]]; then
  cp /app/api_key.conf.sample "${API_KEY_CONF_FILE:-/app/state/api_key.conf}"
  chmod 600 "${API_KEY_CONF_FILE:-/app/state/api_key.conf}" || true
fi

OLLAMA_PID=""
SERVER_PID=""

cleanup() {
  if [[ -n "${SERVER_PID}" ]] && kill -0 "${SERVER_PID}" 2>/dev/null; then
    kill "${SERVER_PID}" 2>/dev/null || true
  fi
  if [[ -n "${OLLAMA_PID}" ]] && kill -0 "${OLLAMA_PID}" 2>/dev/null; then
    kill "${OLLAMA_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

wait_for_ollama() {
  for _ in {1..60}; do
    if curl -fsS --max-time 2 "${OLLAMA_BASE_URL:-http://127.0.0.1:11434}/api/tags" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  echo "Ollama did not become reachable at ${OLLAMA_BASE_URL:-http://127.0.0.1:11434}" >&2
  return 1
}

model_is_installed() {
  local model_name="$1"
  local installed_name
  while read -r installed_name; do
    if [[ "${installed_name}" == "${model_name}" ]]; then
      return 0
    fi
    if [[ "${model_name}" != *:* && "${installed_name}" == "${model_name}:latest" ]]; then
      return 0
    fi
  done < <(ollama list 2>/dev/null | awk 'NR > 1 {print $1}')

  return 1
}

ollama serve >> /app/logs/ollama.log 2>&1 &
OLLAMA_PID="$!"
wait_for_ollama

if [[ "${AUTO_PULL:-1}" == "1" ]] && ! model_is_installed "${OLLAMA_MODEL:-gemma4:31b}"; then
  ollama pull "${OLLAMA_MODEL:-gemma4:31b}"
fi

python3 -u /app/server.py &
SERVER_PID="$!"
wait "${SERVER_PID}"
