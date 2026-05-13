#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEFAULT_ZERO_NATIVE_PATH="${SCRIPT_DIR}/third_party/zero-native"
MISPLACED_ZERO_NATIVE_PATH="${SCRIPT_DIR}/zero-native"
ZERO_NATIVE_PATH_VALUE="${ZERO_NATIVE_PATH:-${DEFAULT_ZERO_NATIVE_PATH}}"
ZERO_NATIVE_ROOT_FILE="${ZERO_NATIVE_PATH_VALUE}/src/root.zig"
STREAMLIT_URL="${STREAMLIT_URL:-http://127.0.0.1:2280}"
STREAMLIT_HOST="${STREAMLIT_HOST:-127.0.0.1}"
STREAMLIT_PORT="${STREAMLIT_PORT:-2280}"
STREAMLIT_LOG_FILE="${SCRIPT_DIR}/.streamlit-app.log"
STARTED_STREAMLIT=0
STREAMLIT_PID=""

cd "${SCRIPT_DIR}"

if [[ -z "${VIRTUAL_ENV:-}" && -f "${SCRIPT_DIR}/.venv/bin/activate" ]]; then
  # Prefer the local project virtualenv when available.
  # shellcheck disable=SC1091
  source "${SCRIPT_DIR}/.venv/bin/activate"
fi

if ! command -v zig >/dev/null 2>&1; then
  echo "zig is not installed or not in PATH." >&2
  echo "Install it first, then run this script again." >&2
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
    result = sock.connect_ex((host, port))
    raise SystemExit(0 if result == 0 else 1)
PY
}

wait_for_streamlit() {
  python3 - "$1" "$2" <<'PY'
import socket
import sys
import time

host = sys.argv[1]
port = int(sys.argv[2])
deadline = time.time() + 45

while time.time() < deadline:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        if sock.connect_ex((host, port)) == 0:
            raise SystemExit(0)
    time.sleep(0.5)

raise SystemExit(1)
PY
}

cleanup() {
  if [[ "${STARTED_STREAMLIT}" == "1" && -n "${STREAMLIT_PID}" ]]; then
    kill "${STREAMLIT_PID}" >/dev/null 2>&1 || true
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
    echo "Move it into the expected framework directory with:" >&2
    echo "  mkdir -p \"${SCRIPT_DIR}/third_party\"" >&2
    echo "  mv \"${MISPLACED_ZERO_NATIVE_PATH}\" \"${DEFAULT_ZERO_NATIVE_PATH}\"" >&2
    echo >&2
  fi
  echo "Fix one of these ways:" >&2
  echo "1. Clone the framework into the default path:" >&2
  echo "   git clone https://github.com/vercel-labs/zero-native.git \"${DEFAULT_ZERO_NATIVE_PATH}\"" >&2
  echo "2. Or point to an existing checkout:" >&2
  echo "   ZERO_NATIVE_PATH=/absolute/path/to/zero-native bash run_zero_native.sh" >&2
  echo "3. Or run zig directly with an override:" >&2
  echo "   zig build run -Dzero-native-path=/absolute/path/to/zero-native" >&2
  exit 1
fi

if port_is_open "${STREAMLIT_HOST}" "${STREAMLIT_PORT}"; then
  echo "Reusing existing Streamlit app at ${STREAMLIT_URL}"
else
  echo "Starting app.py with Streamlit at ${STREAMLIT_URL}"
  STREAMLIT_ADDRESS="${STREAMLIT_HOST}" STREAMLIT_PORT="${STREAMLIT_PORT}" bash "${SCRIPT_DIR}/run.sh" >"${STREAMLIT_LOG_FILE}" 2>&1 &
  STREAMLIT_PID=$!
  STARTED_STREAMLIT=1

  if ! wait_for_streamlit "${STREAMLIT_HOST}" "${STREAMLIT_PORT}"; then
    echo "app.py did not start successfully." >&2
    echo "Check the Streamlit log: ${STREAMLIT_LOG_FILE}" >&2
    exit 1
  fi
fi

export ZERONATIVE_STREAMLIT_URL="${STREAMLIT_URL}"
zig build run -Dzero-native-path="${ZERO_NATIVE_PATH_VALUE}" "$@"
