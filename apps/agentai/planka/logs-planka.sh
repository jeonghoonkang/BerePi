#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"

SERVICE="planka"
TAIL="100"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --service)
      SERVICE="${2:-}"
      shift 2
      ;;
    --tail)
      TAIL="${2:-100}"
      shift 2
      ;;
    --help|-h)
      cat <<'EOF'
Usage: ./logs-planka.sh [--service planka|postgres] [--tail 100]
EOF
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

compose_kind() {
  if docker compose version >/dev/null 2>&1; then
    echo "docker compose"
  elif sudo docker compose version >/dev/null 2>&1; then
    echo "sudo docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"
  elif command -v sudo >/dev/null 2>&1 && sudo docker-compose version >/dev/null 2>&1; then
    echo "sudo docker-compose"
  else
    echo "Docker Compose is not installed." >&2
    echo "Ubuntu 18.04 often needs one of: sudo apt install docker-compose-plugin OR sudo apt install docker-compose." >&2
    exit 1
  fi
}

docker_compose() {
  local kind
  kind="$(compose_kind)"
  (
    cd "${SCRIPT_DIR}"
    case "${kind}" in
      "docker compose")
        docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" "$@"
        ;;
      "sudo docker compose")
        sudo docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" "$@"
        ;;
      "docker-compose")
        docker-compose -f "${COMPOSE_FILE}" "$@"
        ;;
      "sudo docker-compose")
        sudo docker-compose -f "${COMPOSE_FILE}" "$@"
        ;;
    esac
  )
}

args=(logs -f --tail "${TAIL}" "${SERVICE}")

docker_compose "${args[@]}"
