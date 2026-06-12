#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"

compose_kind() {
  if docker info >/dev/null 2>&1; then
    if docker compose version >/dev/null 2>&1; then
      echo "docker compose"
    elif command -v docker-compose >/dev/null 2>&1; then
      echo "docker-compose"
    else
      echo "Docker daemon is available, but Docker Compose is not installed." >&2
      exit 1
    fi
  elif command -v sudo >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; then
    if sudo docker compose version >/dev/null 2>&1; then
      echo "sudo docker compose"
    elif sudo docker-compose version >/dev/null 2>&1; then
      echo "sudo docker-compose"
    else
      echo "Docker daemon is available through sudo, but Docker Compose is not installed for sudo." >&2
      exit 1
    fi
  else
    echo "Cannot access the Docker daemon." >&2
    echo "Start Docker first, or run with a user in the docker group, or use sudo-enabled Docker." >&2
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

args=(ps)

docker_compose "${args[@]}"
