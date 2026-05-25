#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEFAULT_ZERO_NATIVE_PATH="${SCRIPT_DIR}/third_party/zero-native"
MISPLACED_ZERO_NATIVE_PATH="${SCRIPT_DIR}/zero-native"
ZERO_NATIVE_PATH_VALUE="${ZERO_NATIVE_PATH:-${DEFAULT_ZERO_NATIVE_PATH}}"
ZERO_NATIVE_ROOT_FILE="${ZERO_NATIVE_PATH_VALUE}/src/root.zig"
CLIENT_URL="${CLIENT_URL:-http://127.0.0.1:8765}"
CLIENT_HOST="${CLIENT_HOST:-127.0.0.1}"
CLIENT_PORT="${CLIENT_PORT:-8765}"
CLIENT_LOG_FILE="${SCRIPT_DIR}/data/client-service.log"
STARTED_CLIENT=0
CLIENT_PID=""

cd "${SCRIPT_DIR}"
mkdir -p "${SCRIPT_DIR}/data"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is not installed or not in PATH." >&2
  exit 1
fi

if ! command -v zig >/dev/null 2>&1; then
  echo "zig is not installed or not in PATH." >&2
  echo "macOS example: brew install zig" >&2
  exit 1
fi

port_is_open() {
  python3 - "$1" "$2" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.settimeout(0.5)
    raise SystemExit(0 if sock.connect_ex((host, port)) == 0 else 1)
PY
}

wait_for_client() {
  python3 - "$1" "$2" <<'PY'
import socket
import sys
import time

host = sys.argv[1]
port = int(sys.argv[2])
deadline = time.time() + 30

while time.time() < deadline:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        if sock.connect_ex((host, port)) == 0:
            raise SystemExit(0)
    time.sleep(0.4)

raise SystemExit(1)
PY
}

cleanup() {
  if [[ "${STARTED_CLIENT}" == "1" && -n "${CLIENT_PID}" ]]; then
    kill "${CLIENT_PID}" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT

if [[ ! -f "${ZERO_NATIVE_ROOT_FILE}" ]]; then
  echo "zero-native framework source was not found." >&2
  echo "Expected file: ${ZERO_NATIVE_ROOT_FILE}" >&2
  echo >&2
  if [[ "${ZERO_NATIVE_PATH_VALUE}" == "${DEFAULT_ZERO_NATIVE_PATH}" ]] && [[ -f "${MISPLACED_ZERO_NATIVE_PATH}/src/root.zig" ]]; then
    echo "A zero-native checkout was found in the app root instead:" >&2
    echo "  ${MISPLACED_ZERO_NATIVE_PATH}" >&2
    echo >&2
  fi
  echo "Clone the framework into the default path:" >&2
  echo "  git clone https://github.com/vercel-labs/zero-native.git \"${DEFAULT_ZERO_NATIVE_PATH}\"" >&2
  echo "Or override it:" >&2
  echo "  ZERO_NATIVE_PATH=/absolute/path/to/zero-native ./run_zero_native.sh" >&2
  exit 1
fi

if port_is_open "${CLIENT_HOST}" "${CLIENT_PORT}"; then
  echo "Reusing existing client service at ${CLIENT_URL}"
else
  echo "Starting local client service at ${CLIENT_URL}"
  GEMMA4_CLIENT_HOST="${CLIENT_HOST}" GEMMA4_CLIENT_PORT="${CLIENT_PORT}" \
    python3 "${SCRIPT_DIR}/client_service.py" >"${CLIENT_LOG_FILE}" 2>&1 &
  CLIENT_PID=$!
  STARTED_CLIENT=1
  if ! wait_for_client "${CLIENT_HOST}" "${CLIENT_PORT}"; then
    echo "client_service.py did not start successfully." >&2
    echo "Check the log: ${CLIENT_LOG_FILE}" >&2
    exit 1
  fi
fi

zig build run -Dzero-native-path="${ZERO_NATIVE_PATH_VALUE}" "$@"
