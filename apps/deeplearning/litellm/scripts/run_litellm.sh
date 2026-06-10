#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--remote] [--host HOST] [--port PORT]

Starts LiteLLM proxy with config.yaml.

Examples:
  $(basename "$0")
  $(basename "$0") --remote
  $(basename "$0") --host 0.0.0.0 --port 4001
EOF
}

load_env

HOST="${LITELLM_HOST:-127.0.0.1}"
PORT="${LITELLM_PORT:-4000}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --remote)
      HOST="0.0.0.0"
      shift
      ;;
    --host)
      HOST="${2:-}"
      shift 2
      ;;
    --port)
      PORT="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ! "${PORT}" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
  echo "Invalid port: ${PORT}" >&2
  exit 2
fi

ensure_python
require_command litellm
ensure_master_key

export GOOGLE_GEMMA4_VLLM_API_BASE="${GOOGLE_GEMMA4_VLLM_API_BASE:-http://127.0.0.1:8001/v1}"
export NVIDIA_GEMMA4_NVFP4_VLLM_API_BASE="${NVIDIA_GEMMA4_NVFP4_VLLM_API_BASE:-http://127.0.0.1:8002/v1}"
export VLLM_API_KEY="${VLLM_API_KEY:-none}"
export LITELLM_ALLOWED_IPS="${LITELLM_ALLOWED_IPS:-}"
ensure_port_available "${PORT}" "LiteLLM"

RUNTIME_DIR="${APP_DIR}/.runtime"
RUNTIME_CONFIG="${RUNTIME_DIR}/config.yaml"
mkdir -p "${RUNTIME_DIR}"
"${PYTHON_BIN}" -c 'import json, os, sys
source, target = sys.argv[1], sys.argv[2]
text = open(source, encoding="utf-8").read()
ips = [item.strip() for item in os.getenv("LITELLM_ALLOWED_IPS", "").split(",") if item.strip()]
marker = "  # Optional LiteLLM IP filtering can be enabled by adding:\n  # allowed_ips: [\"127.0.0.1\", \"192.168.0.10\"]"
replacement = marker
if ips:
    replacement = "  allowed_ips: " + json.dumps(ips)
open(target, "w", encoding="utf-8").write(text.replace(marker, replacement))
' "${APP_DIR}/config.yaml" "${RUNTIME_CONFIG}"

print_auth_hint
if [[ -n "${LITELLM_ALLOWED_IPS}" ]]; then
  echo
  echo "LiteLLM IP allowlist: ${LITELLM_ALLOWED_IPS}"
fi
echo
echo "Starting LiteLLM at http://${HOST}:${PORT}"
echo "Config: ${RUNTIME_CONFIG}"

exec litellm \
  --config "${RUNTIME_CONFIG}" \
  --host "${HOST}" \
  --port "${PORT}"
