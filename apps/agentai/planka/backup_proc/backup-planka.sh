#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLANKA_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKUP_ROOT="${SCRIPT_DIR}/backups"
KEEP_LAST=10
SKIP_DATA=0

usage() {
  cat <<'USAGE'
Usage: ./backup-planka.sh [--backup-root PATH] [--keep-last N] [--skip-data]
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

echo "Backup complete: ${BACKUP_DIR}"
