#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
SAMPLE_FILE="${SCRIPT_DIR}/.env.sample"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"

PULL=0
FOREGROUND=0

for arg in "$@"; do
  case "${arg}" in
    --pull)
      PULL=1
      ;;
    --foreground|-f)
      FOREGROUND=1
      ;;
    --help|-h)
      cat <<'EOF'
Usage: ./start-planka.sh [--pull] [--foreground]

Options:
  --pull         Pull PLANKA/PostgreSQL images before starting.
  --foreground   Run docker compose in the foreground.
EOF
      exit 0
      ;;
    *)
      echo "Unknown argument: ${arg}" >&2
      exit 1
      ;;
  esac
done

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
  echo "Using Compose command: ${kind}" >&2
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

docker_cmd() {
  if docker info >/dev/null 2>&1; then
    docker "$@"
  else
    sudo docker "$@"
  fi
}

wait_for_postgres() {
  local container_id
  local status
  local attempt

  container_id="$(docker_compose ps -q postgres)"
  if [[ -z "${container_id}" ]]; then
    echo "PostgreSQL container was not created." >&2
    exit 1
  fi

  echo "Waiting for PostgreSQL to become healthy..."
  for attempt in $(seq 1 60); do
    status="$(docker_cmd inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${container_id}" 2>/dev/null || true)"
    if [[ "${status}" == "healthy" || "${status}" == "running" ]]; then
      echo "PostgreSQL status: ${status}"
      return 0
    fi
    echo "PostgreSQL status: ${status:-unknown} (${attempt}/60)"
    sleep 2
  done

  echo "PostgreSQL did not become ready in time. Showing logs:" >&2
  docker_compose logs --tail 80 postgres >&2 || true
  exit 1
}

new_secret_key() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 64
  else
    python3 - <<'PY'
import secrets
print(secrets.token_hex(64))
PY
  fi
}

if [[ ! -f "${ENV_FILE}" ]]; then
  cp "${SAMPLE_FILE}" "${ENV_FILE}"
  secret="$(new_secret_key)"
  sed -i "s/SECRET_KEY=replace_with_64_byte_hex_secret/SECRET_KEY=${secret}/" "${ENV_FILE}"
  echo "Created .env with a generated SECRET_KEY."
  echo "Edit .env if you want a different port, base URL, or admin account."
fi

if [[ "${PULL}" == "1" ]]; then
  docker_compose pull
fi

echo "Checking Docker Compose configuration..."
docker_compose config >/dev/null

args=(up)
if [[ "${FOREGROUND}" != "1" ]]; then
  args+=(-d)
fi

echo "Starting PostgreSQL..."
docker_compose up -d postgres
wait_for_postgres

echo "Starting PLANKA..."
docker_compose "${args[@]}"

base_url="$(grep -E '^BASE_URL=' "${ENV_FILE}" | tail -n 1 | cut -d= -f2-)"
base_url="${base_url:-http://localhost:3000}"

echo
echo "PLANKA URL:"
echo "${base_url}"
echo
docker_compose ps
