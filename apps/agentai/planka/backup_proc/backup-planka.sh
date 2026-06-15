#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLANKA_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKUP_ROOT="${SCRIPT_DIR}/backups"
KEEP_LAST=10
SKIP_DATA=0
REMOTE_ROOT="user@10.0.0.53:backup/planka"
SKIP_REMOTE_COPY=0

usage() {
  cat <<'USAGE'
Usage: ./backup-planka.sh [--backup-root PATH] [--keep-last N] [--skip-data] [--remote-root USER@HOST:PATH] [--skip-remote-copy]
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --backup-root)
      BACKUP_ROOT="$2"
      shift 2
      ;;
    --keep-last)
      KEEP_LAST="$2"
      shift 2
      ;;
    --skip-data)
      SKIP_DATA=1
      shift
      ;;
    --remote-root)
      REMOTE_ROOT="$2"
      shift 2
      ;;
    --skip-remote-copy)
      SKIP_REMOTE_COPY=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 1
      ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker was not found in PATH." >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  compose() {
    docker compose --project-directory "${PLANKA_DIR}" "$@"
  }
elif command -v docker-compose >/dev/null 2>&1; then
  compose() {
    docker-compose --project-directory "${PLANKA_DIR}" "$@"
  }
else
  echo "Neither 'docker compose' nor 'docker-compose' is available." >&2
  exit 1
fi

LOCAL_MACHINE_NAME="$(hostname -s 2>/dev/null || hostname 2>/dev/null || echo unknown)"
LOCAL_MACHINE_NAME="$(printf '%s' "${LOCAL_MACHINE_NAME}" | tr -c 'A-Za-z0-9._-' '_')"

copy_backup_to_remote() {
  local backup_dir="$1"
  local remote_root="$2"
  local machine_name="$3"

  if [[ "${remote_root}" != *:* ]]; then
    echo "Remote root must use USER@HOST:PATH format: ${remote_root}" >&2
    exit 1
  fi

  local remote_host="${remote_root%%:*}"
  local remote_path="${remote_root#*:}"
  local remote_machine_path="${remote_path}/${machine_name}"

  if ! command -v ssh >/dev/null 2>&1; then
    echo "ssh was not found in PATH. Install OpenSSH or run with --skip-remote-copy." >&2
    exit 1
  fi

  echo "Copying backup to ${remote_host}:${remote_machine_path}/"
  ssh "${remote_host}" "mkdir -p '${remote_machine_path}'"

  if command -v rsync >/dev/null 2>&1; then
    rsync -az --delete "${backup_dir}/" "${remote_host}:${remote_machine_path}/$(basename "${backup_dir}")/"
  elif command -v scp >/dev/null 2>&1; then
    scp -r "${backup_dir}" "${remote_host}:${remote_machine_path}/"
  else
    echo "Neither rsync nor scp was found in PATH. Install one or run with --skip-remote-copy." >&2
    exit 1
  fi
}

mkdir -p "${BACKUP_ROOT}"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="${BACKUP_ROOT}/planka-${TIMESTAMP}"
mkdir -p "${BACKUP_DIR}"

echo "Creating PLANKA backup: ${BACKUP_DIR}"

POSTGRES_CONTAINER="$(compose ps -q postgres)"
if [ -z "${POSTGRES_CONTAINER}" ]; then
  echo "PostgreSQL container was not found. Start PLANKA before running backup." >&2
  exit 1
fi

PLANKA_CONTAINER="$(compose ps -q planka)"
if [ -z "${PLANKA_CONTAINER}" ] && [ "${SKIP_DATA}" -eq 0 ]; then
  echo "PLANKA container was not found. Start PLANKA or use --skip-data." >&2
  exit 1
fi

write_container_stack_info() {
  local service_name="$1"
  local container_id="$2"

  echo "## ${service_name}"
  if [ -z "${container_id}" ]; then
    echo "container: not running"
    echo
    return
  fi

  docker inspect --format 'container_id: {{.Id}}' "${container_id}"
  docker inspect --format 'configured_image: {{.Config.Image}}' "${container_id}"
  docker inspect --format 'image_id: {{.Image}}' "${container_id}"
  docker inspect --format 'image_labels: {{json .Config.Labels}}' "${container_id}"
  docker inspect --format 'created: {{.Created}}' "${container_id}"
  echo
}

echo "Writing stack version info..."
{
  echo "# PLANKA stack info"
  echo "backup_timestamp: ${TIMESTAMP}"
  echo "backup_host: ${LOCAL_MACHINE_NAME}"
  echo "planka_dir: ${PLANKA_DIR}"
  echo

  echo "## Docker"
  echo "docker_client: $(docker version --format '{{.Client.Version}}' 2>/dev/null || echo unavailable)"
  echo "docker_server: $(docker version --format '{{.Server.Version}}' 2>/dev/null || echo unavailable)"
  echo "compose: $(compose version 2>/dev/null | head -n 1 || echo unavailable)"
  echo

  echo "## PostgreSQL database"
  echo "server_version: $(compose exec -T postgres psql -U postgres -d postgres -Atc 'SHOW server_version;' 2>/dev/null || echo unavailable)"
  echo "server_version_num: $(compose exec -T postgres psql -U postgres -d postgres -Atc 'SHOW server_version_num;' 2>/dev/null || echo unavailable)"
  echo "pg_dump: $(compose exec -T postgres pg_dump --version 2>/dev/null || echo unavailable)"
  echo "pg_restore: $(compose exec -T postgres pg_restore --version 2>/dev/null || echo unavailable)"
  echo

  write_container_stack_info "planka container" "${PLANKA_CONTAINER}"
  write_container_stack_info "postgres container" "${POSTGRES_CONTAINER}"
} > "${BACKUP_DIR}/stack-info.txt"

cp "${PLANKA_DIR}/docker-compose.yml" "${BACKUP_DIR}/"
cp "${PLANKA_DIR}/.env.sample" "${BACKUP_DIR}/"
if [ -f "${PLANKA_DIR}/.env" ]; then
  cp "${PLANKA_DIR}/.env" "${BACKUP_DIR}/"
fi

DUMP_NAME="planka-${TIMESTAMP}.dump"
DUMP_IN_CONTAINER="/tmp/${DUMP_NAME}"

echo "Dumping PostgreSQL database..."
compose exec -T postgres pg_dump -U postgres -d planka -Fc -f "${DUMP_IN_CONTAINER}"
docker cp "${POSTGRES_CONTAINER}:${DUMP_IN_CONTAINER}" "${BACKUP_DIR}/postgres.dump"
compose exec -T postgres rm -f "${DUMP_IN_CONTAINER}"

if [ "${SKIP_DATA}" -eq 0 ]; then
  echo "Archiving PLANKA data volume..."
  DATA_VOLUME="$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/app/data"}}{{.Name}}{{end}}{{end}}' "${PLANKA_CONTAINER}")"
  if [ -z "${DATA_VOLUME}" ]; then
    echo "Could not find the Docker volume mounted at /app/data." >&2
    exit 1
  fi

  docker run --rm \
    -v "${DATA_VOLUME}:/data:ro" \
    -v "${BACKUP_DIR}:/backup" \
    alpine:3.20 \
    sh -c 'cd /data && tar -czf /backup/planka-data.tar.gz .'
fi

echo "Writing checksum manifest..."
(
  cd "${BACKUP_DIR}"
  if command -v sha256sum >/dev/null 2>&1; then
    find . -maxdepth 1 -type f ! -name manifest.sha256 -printf '%f\n' | sort | xargs -r sha256sum > manifest.sha256
  else
    find . -maxdepth 1 -type f ! -name manifest.sha256 -print | sort | xargs shasum -a 256 > manifest.sha256
  fi
)

if [ "${KEEP_LAST}" -gt 0 ]; then
  find "${BACKUP_ROOT}" -maxdepth 1 -type d -name 'planka-*' -printf '%f\n' |
    sort -r |
    awk "NR>${KEEP_LAST}" |
    while IFS= read -r old_backup; do
      rm -rf "${BACKUP_ROOT}/${old_backup}"
    done
fi

if [ "${SKIP_REMOTE_COPY}" -eq 0 ]; then
  copy_backup_to_remote "${BACKUP_DIR}" "${REMOTE_ROOT}" "${LOCAL_MACHINE_NAME}"
fi

echo "Backup complete: ${BACKUP_DIR}"
