#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${APP_DIR}/.env"
SECRETS_DIR="${APP_DIR}/.secrets"

load_env() {
  if [[ -f "${ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
  fi
}

find_python_bin() {
  local candidates=()
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    candidates+=("${PYTHON_BIN}")
  fi
  candidates+=(python3 python py /mnt/c/Windows/py.exe)

  local candidate
  for candidate in "${candidates[@]}"; do
    if ! command -v "${candidate}" >/dev/null 2>&1; then
      continue
    fi
    if "${candidate}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  return 1
}

ensure_python() {
  if ! PYTHON_BIN="$(find_python_bin)"; then
    echo "Python 3.9+ is required. Set PYTHON_BIN=/path/to/python if needed." >&2
    exit 1
  fi
  export PYTHON_BIN
}

ensure_master_key() {
  if [[ -n "${LITELLM_MASTER_KEY:-}" && "${LITELLM_MASTER_KEY}" != "sk-change-this-litellm-master-key" ]]; then
    return 0
  fi

  mkdir -p "${SECRETS_DIR}"
  chmod 700 "${SECRETS_DIR}" 2>/dev/null || true
  local key_file="${SECRETS_DIR}/litellm_master_key"
  if [[ ! -f "${key_file}" ]]; then
    "${PYTHON_BIN}" -c 'import secrets; print("sk-" + secrets.token_hex(32))' > "${key_file}"
    chmod 600 "${key_file}" 2>/dev/null || true
  fi
  export LITELLM_MASTER_KEY
  LITELLM_MASTER_KEY="$(tr -d '[:space:]' < "${key_file}")"
}

require_command() {
  local name="$1"
  if ! command -v "${name}" >/dev/null 2>&1; then
    echo "Missing required command: ${name}" >&2
    exit 1
  fi
}

port_is_open() {
  "${PYTHON_BIN}" -c 'import socket, sys; port = int(sys.argv[1]); sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM); sock.settimeout(1); raise SystemExit(0 if sock.connect_ex(("127.0.0.1", port)) == 0 else 1)' "$1"
}

ensure_port_available() {
  local port="$1"
  local label="$2"
  if port_is_open "${port}"; then
    echo "${label} port ${port} is already in use." >&2
    exit 1
  fi
}

print_auth_hint() {
  cat <<EOF
LiteLLM master key:
  ${LITELLM_MASTER_KEY}

Clients must send:
  Authorization: Bearer ${LITELLM_MASTER_KEY}
EOF
}
