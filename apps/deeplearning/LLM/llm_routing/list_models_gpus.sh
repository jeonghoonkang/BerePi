#!/usr/bin/env bash
# Query only the routing status API; never submit prompts or alter targets.
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: bash list_models_gpus.sh [BASE_URL] [--json]
  BASE_URL                    Default: http://127.0.0.1:4004
  --json                      Print the summarized report as JSON
  LLM_ROUTING_URL             Alternative default URL
  LLM_ROUTING_PASSWORD        Optional routing password for detailed status
  LLM_ROUTING_STATUS_TIMEOUT  curl timeout in seconds (default: 120)

Examples:
  bash list_models_gpus.sh http://10.0.0.24:4004
  bash list_models_gpus.sh http://10.0.0.24:4004 --json
EOF
}

url=${LLM_ROUTING_URL:-http://127.0.0.1:4004}
format=()
url_given=false
for arg in "$@"; do
    case "$arg" in
        -h|--help) usage; exit 0 ;;
        --json) format=(--json) ;;
        http://*|https://*)
            if "$url_given"; then usage >&2; exit 2; fi
            url=$arg
            url_given=true ;;
        *) printf 'Unknown argument: %s\n' "$arg" >&2; usage >&2; exit 2 ;;
    esac
done
case "$url" in
    http://*|https://*) ;;
    *) printf 'URL must start with http:// or https://\n' >&2; exit 2 ;;
esac
command -v curl >/dev/null || { printf 'curl is required\n' >&2; exit 127; }
command -v python3 >/dev/null || { printf 'python3 is required\n' >&2; exit 127; }
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

# Pass the password through stdin config, not process arguments or a temp file.
auth_config() {
    local password=${LLM_ROUTING_PASSWORD:-}
    if [[ "$password" == *$'\n'* || "$password" == *$'\r'* ]]; then
        printf 'Password must not contain a newline\n' >&2
        return 2
    fi
    if [[ -n "$password" ]]; then
        password=${password//\\/\\\\}
        password=${password//\"/\\\"}
        printf 'header = "X-LLM-Routing-Password: %s"\n' "$password"
    fi
}

auth_config |
    curl --config - --silent --show-error --fail --connect-timeout 5 \
        --max-time "${LLM_ROUTING_STATUS_TIMEOUT:-120}" \
        --header 'Accept: application/json' "${url%/}/api/status" |
    python3 "$script_dir/format_models_gpus.py" "${format[@]}"
