#!/usr/bin/env bash
set -euo pipefail
umask 077
APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$(uname -s)" != Linux || "$(uname -m)" != aarch64 ]]; then
  echo 'This launcher requires 64-bit ARM Linux.' >&2
  exit 1
fi
if [[ ! -f "$APP_DIR/config.env" ]]; then
  echo 'Run bash install.sh first to create config.env.' >&2
  exit 1
fi
set -a
# Trusted, owner-controlled configuration; never use a downloaded config file.
source "$APP_DIR/config.env"
set +a
export GEMMA4_SERVER_HOST="${GEMMA4_SERVER_HOST:-0.0.0.0}"
export GEMMA4_SERVER_PORT="${GEMMA4_SERVER_PORT:-8082}"
export OLLAMA_HOST="127.0.0.1:${OLLAMA_PORT:-11435}"
export OLLAMA_BASE_URL="http://${OLLAMA_HOST}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-gemma4:e4b}"
export OLLAMA_MODELS="${OLLAMA_MODELS:-$APP_DIR/models}"
export OLLAMA_CONTEXT_LENGTH="${OLLAMA_CONTEXT_LENGTH:-2048}"
export OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:-5m}"
# Dedicated CPU daemon: do not inherit workstation parallelism / GPU settings.
export OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_MAX_QUEUE=1
export CUDA_VISIBLE_DEVICES=-1 ROCR_VISIBLE_DEVICES=-1 OLLAMA_NO_CLOUD=1
export NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost
for tool in python3 curl ollama flock; do
  command -v "$tool" >/dev/null || { echo "Missing $tool; run install.sh" >&2; exit 1; }
done
mkdir -p "$APP_DIR/logs" "$OLLAMA_MODELS"
exec 9>"$APP_DIR/logs/run.lock"
flock -n 9 || { echo 'This server directory is already running.' >&2; exit 1; }
cd "$APP_DIR"
python3 - <<'PY'
import os
import socket
from pathlib import Path
from server import Config

config = Config()
for host, port in [(config.host, config.port), ('127.0.0.1', int(os.getenv('OLLAMA_PORT', '11435')))]:
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
memory = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:')))
if memory < 14 * 1024 * 1024:
    print('WARNING: E4B download is about 9.6 GB; a 16 GB Pi 5 is recommended. Low RAM may cause inference failure.', flush=True)
PY
OLLAMA_PID='' SERVER_PID='' PULL_PID=''
cleanup() {
  local pid
  trap - EXIT INT TERM
  for pid in "$SERVER_PID" "$PULL_PID" "$OLLAMA_PID"; do
    if [[ -n "$pid" ]]; then kill "$pid" 2>/dev/null || true; fi
  done
  for _ in {1..10}; do
    local alive=0
    for pid in "$SERVER_PID" "$PULL_PID" "$OLLAMA_PID"; do
      if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then alive=1; fi
    done
    (( alive == 0 )) && break
    sleep 1
  done
  for pid in "$SERVER_PID" "$PULL_PID" "$OLLAMA_PID"; do
    if [[ -n "$pid" ]]; then
      kill -KILL "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
ollama serve >>"$APP_DIR/logs/ollama.log" 2>&1 &
OLLAMA_PID=$!
ready=0
echo "Waiting for Ollama: $OLLAMA_BASE_URL ..."
for _ in {1..60}; do
  kill -0 "$OLLAMA_PID" 2>/dev/null || { echo 'Ollama exited; see logs/ollama.log' >&2; exit 1; }
  if curl -fsS --max-time 2 "$OLLAMA_BASE_URL/api/tags" >/dev/null 2>"$APP_DIR/logs/ollama-readiness.log"; then ready=1; break; fi
  sleep 1
done
if (( ready != 1 )); then
  echo 'Ollama startup timed out; see logs/ollama.log' >&2
  cat "$APP_DIR/logs/ollama-readiness.log" >&2
  exit 1
fi
echo "Ollama API ready: $OLLAMA_BASE_URL"
if ! ollama show "$OLLAMA_MODEL" >/dev/null 2>&1; then
  if [[ "${AUTO_PULL:-1}" != 1 ]]; then
    echo "Model missing: $OLLAMA_MODEL; set AUTO_PULL=1 for the first start." >&2
    exit 1
  fi
  echo "Downloading $OLLAMA_MODEL to $OLLAMA_MODELS ..."
  ollama pull "$OLLAMA_MODEL" &
  PULL_PID=$!
  wait "$PULL_PID"
  PULL_PID=''
fi
python3 -u "$APP_DIR/server.py" &
SERVER_PID=$!
# If either child fails, stop its sibling and let systemd restart this service.
set +e
wait -n "$OLLAMA_PID" "$SERVER_PID"
status=$?
set -e
(( status != 0 )) || status=1
exit "$status"
