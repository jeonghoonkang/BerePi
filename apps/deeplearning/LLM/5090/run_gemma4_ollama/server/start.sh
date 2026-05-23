#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${APP_DIR}/logs"
PID_FILE="${APP_DIR}/server.pid"
OLLAMA_PID_FILE="${APP_DIR}/ollama.pid"
GPU_SELECTION_FILE="${APP_DIR}/gpu-selection"
MODEL_SELECTION_FILE="${APP_DIR}/model-selection"
mkdir -p "${LOG_DIR}"

export OLLAMA_MODEL="${OLLAMA_MODEL:-gemma4:31b}"
export OLLAMA_CONTEXT_LENGTH="${OLLAMA_CONTEXT_LENGTH:-8192}"
export OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:-60m}"
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
export GEMMA4_SERVER_HOST="${GEMMA4_SERVER_HOST:-0.0.0.0}"
export GEMMA4_SERVER_PORT="${GEMMA4_SERVER_PORT:-8082}"
export OLLAMA_PID_FILE
export GPU_SELECTION_FILE
export MODEL_SELECTION_FILE
export AUTO_PULL="${AUTO_PULL:-1}"

find_ollama_bin() {
  if [[ -n "${OLLAMA_BIN:-}" ]] && [[ -x "${OLLAMA_BIN}" ]]; then
    printf '%s\n' "${OLLAMA_BIN}"
    return 0
  fi

  if command -v ollama >/dev/null 2>&1; then
    command -v ollama
    return 0
  fi

  for candidate in /usr/local/bin/ollama /opt/homebrew/bin/ollama; do
    if [[ -x "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  return 1
}

start_detached() {
  local log_file="$1"
  shift
  if command -v setsid >/dev/null 2>&1; then
    nohup setsid "$@" > "${log_file}" 2>&1 &
  else
    nohup "$@" > "${log_file}" 2>&1 &
  fi
  echo "$!"
}

install_ollama() {
  if ! command -v curl >/dev/null 2>&1; then
    echo "Ollama is not installed, and curl is required to install it." >&2
    exit 1
  fi

  echo "${1:-Installing Ollama...}"
  curl -fsSL https://ollama.com/install.sh | sh
}

if ! OLLAMA_BIN="$(find_ollama_bin)"; then
  install_ollama "Ollama is not installed. Installing Ollama..."
  if ! OLLAMA_BIN="$(find_ollama_bin)"; then
    echo "Ollama installation finished, but the ollama command was not found." >&2
    exit 1
  fi
fi
export OLLAMA_BIN

stop_ollama_pid() {
  local pid="$1"
  if kill -0 "${pid}" 2>/dev/null; then
    kill "${pid}" 2>/dev/null || true
    for _ in {1..10}; do
      if ! kill -0 "${pid}" 2>/dev/null; then
        return 0
      fi
      sleep 1
    done
    kill -9 "${pid}" 2>/dev/null || true
  fi
}

wait_until_ollama_stops() {
  for _ in {1..10}; do
    if ! curl -fsS --max-time 2 "${OLLAMA_BASE_URL}/api/tags" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  echo "Ollama is still reachable at ${OLLAMA_BASE_URL} after restart attempt." >&2
  return 1
}

stop_started_ollama() {
  if [[ -f "${OLLAMA_PID_FILE}" ]]; then
    local pid
    pid="$(cat "${OLLAMA_PID_FILE}")"
    stop_ollama_pid "${pid}"
    rm -f "${OLLAMA_PID_FILE}"
  fi
}

stop_all_ollama_processes() {
  stop_started_ollama

  if command -v pgrep >/dev/null 2>&1; then
    local pid
    while read -r pid; do
      [[ -n "${pid}" ]] && stop_ollama_pid "${pid}"
    done < <(pgrep -x ollama 2>/dev/null || true)
  fi

  wait_until_ollama_stops
}

wait_for_ollama() {
  for _ in {1..30}; do
    if curl -fsS --max-time 2 "${OLLAMA_BASE_URL}/api/tags" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  echo "Ollama did not become reachable at ${OLLAMA_BASE_URL}" >&2
  return 1
}

cuda_device_for_gpu_selection() {
  local selected="$1"
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    printf '%s\n' "${selected}"
    return 0
  fi

  local index uuid
  while IFS=, read -r index uuid; do
    index="$(echo "${index}" | xargs)"
    uuid="$(echo "${uuid}" | xargs)"
    if [[ "${index}" == "${selected}" && -n "${uuid}" ]]; then
      printf '%s\n' "${uuid}"
      return 0
    fi
  done < <(nvidia-smi --query-gpu=index,uuid --format=csv,noheader,nounits 2>/dev/null || true)

  printf '%s\n' "${selected}"
}

apply_gpu_selection() {
  local selected="auto"
  if [[ -f "${GPU_SELECTION_FILE}" ]]; then
    selected="$(tr -d '[:space:]' < "${GPU_SELECTION_FILE}")"
  fi

  case "${selected}" in
    ""|"auto"|"all")
      unset CUDA_VISIBLE_DEVICES
      ;;
    "cpu"|"none")
      export CUDA_VISIBLE_DEVICES="-1"
      ;;
    *)
      export CUDA_VISIBLE_DEVICES="$(cuda_device_for_gpu_selection "${selected}")"
      ;;
  esac
}

apply_model_selection() {
  if [[ -f "${MODEL_SELECTION_FILE}" ]]; then
    local selected
    selected="$(tr -d '[:space:]' < "${MODEL_SELECTION_FILE}")"
    if [[ -n "${selected}" ]]; then
      export OLLAMA_MODEL="${selected}"
    fi
  fi
}

start_ollama_if_needed() {
  if curl -fsS --max-time 2 "${OLLAMA_BASE_URL}/api/tags" >/dev/null 2>&1; then
    echo "Ollama is already running at ${OLLAMA_BASE_URL}."
    echo "To stop the existing Ollama service, run: sudo systemctl stop ollama"
  else
    apply_gpu_selection
    start_detached "${LOG_DIR}/ollama.log" "${OLLAMA_BIN}" serve > "${OLLAMA_PID_FILE}"
  fi
  wait_for_ollama
}

restart_started_ollama() {
  stop_all_ollama_processes
  apply_gpu_selection
  start_detached "${LOG_DIR}/ollama.log" "${OLLAMA_BIN}" serve > "${OLLAMA_PID_FILE}"
  wait_for_ollama
}

pull_ollama_model() {
  local output_file
  output_file="$(mktemp)"

  if "${OLLAMA_BIN}" pull "${OLLAMA_MODEL}" 2>&1 | tee "${output_file}"; then
    rm -f "${output_file}"
    return 0
  fi

  if grep -qi "requires a newer version of Ollama" "${output_file}"; then
    rm -f "${output_file}"
    install_ollama "Ollama is too old for ${OLLAMA_MODEL}. Updating Ollama..."
    if ! OLLAMA_BIN="$(find_ollama_bin)"; then
      echo "Ollama update finished, but the ollama command was not found." >&2
      exit 1
    fi
    export OLLAMA_BIN
    restart_started_ollama
    "${OLLAMA_BIN}" pull "${OLLAMA_MODEL}"
    return
  fi

  rm -f "${output_file}"
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
  done < <("${OLLAMA_BIN}" list 2>/dev/null | awk 'NR > 1 {print $1}')

  return 1
}

ensure_ollama_model() {
  if model_is_installed "${OLLAMA_MODEL}"; then
    echo "Ollama model ${OLLAMA_MODEL} is already installed. Skipping download."
    return 0
  fi

  pull_ollama_model
}

if [[ -f "${PID_FILE}" ]] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
  echo "Gemma4 service is already running with PID $(cat "${PID_FILE}")"
  exit 0
fi

start_ollama_if_needed

apply_model_selection

if [[ "${AUTO_PULL}" == "1" ]]; then
  ensure_ollama_model
fi

start_detached "${LOG_DIR}/server.log" python3 -u "${APP_DIR}/server.py" > "${PID_FILE}"
echo "Started Gemma4 service with PID $(cat "${PID_FILE}")"
echo "Open http://localhost:8082"
