#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLANKA_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKUP_DIR=""
YES=0
SKIP_DB=0
SKIP_DATA=0
RESTORE_ENV=0

usage() {
  cat <<'USAGE'
Usage: ./restore-planka.sh BACKUP_DIR [--yes] [--skip-db] [--skip-data] [--restore-env]

Examples:
  ./restore-planka.sh ./backups/planka-20260616-120000
  ./restore-planka.sh /mnt/backups/planka/planka-20260616-120000 --yes
  ./restore-planka.sh ./backups/planka-20260616-120000 --skip-data

Options:
  --yes          Do not ask for destructive restore confirmation.
  --skip-db      Do not restore PostgreSQL.
  --skip-data    Do not restore the PLANKA /app/data volume.
  --restore-env  Replace current .env with the backup copy when present.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --yes)
      YES=1
      shift
      ;;
    --skip-db)
      SKIP_DB=1
      shift
      ;;
    --skip-data)
      SKIP_DATA=1
      shift
      ;;
    --restore-env)
      RESTORE_ENV=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      usage >&2
      exit 1
      ;;
    *)
      if [ -n "${BACKUP_DIR}" ]; then
        usage >&2
        exit 1
      fi
      BACKUP_DIR="$1"
      shift
      ;;
  esac
done

if [ -z "${BACKUP_DIR}" ]; then
  usage >&2
  exit 1
fi

BACKUP_DIR="$(cd "${BACKUP_DIR}" && pwd)"

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

if [ "${SKIP_DB}" -eq 0 ] && [ ! -f "${BACKUP_DIR}/postgres.dump" ]; then
  echo "Missing required file: ${BACKUP_DIR}/postgres.dump" >&2
  exit 1
fi

if [ "${SKIP_DATA}" -eq 0 ] && [ ! -f "${BACKUP_DIR}/planka-data.tar.gz" ]; then
  echo "Missing required file: ${BACKUP_DIR}/planka-data.tar.gz" >&2
  exit 1
fi

if [ -f "${BACKUP_DIR}/manifest.sha256" ]; then
  echo "Verifying checksum manifest..."
  (
    cd "${BACKUP_DIR}"
    if command -v sha256sum >/dev/null 2>&1; then
      sha256sum -c manifest.sha256
    else
      shasum -a 256 -c manifest.sha256
    fi
  )
fi

cat <<EOF
This will restore PLANKA from:
  ${BACKUP_DIR}

Target app directory:
  ${PLANKA_DIR}

Existing PostgreSQL data and/or PLANKA uploaded data will be replaced.
EOF

if [ "${YES}" -ne 1 ]; then
  printf "Type RESTORE to continue: "
  read -r answer
  if [ "${answer}" != "RESTORE" ]; then
    echo "Restore cancelled."
    exit 1
  fi
fi

if [ "${RESTORE_ENV}" -eq 1 ]; then
  if [ -f "${BACKUP_DIR}/.env" ]; then
    echo "Restoring .env..."
    cp "${BACKUP_DIR}/.env" "${PLANKA_DIR}/.env"
  else
    echo "Backup does not contain .env; skipping .env restore."
  fi
fi

echo "Stopping PLANKA application container..."
compose stop planka >/dev/null 2>&1 || true

if [ "${SKIP_DB}" -eq 0 ]; then
  echo "Starting PostgreSQL service..."
  compose up -d postgres

  POSTGRES_CONTAINER="$(compose ps -q postgres)"
  if [ -z "${POSTGRES_CONTAINER}" ]; then
    echo "PostgreSQL container was not found after startup." >&2
    exit 1
  fi

  echo "Waiting for PostgreSQL to become ready..."
  for _ in $(seq 1 60); do
    if compose exec -T postgres pg_isready -U postgres -d postgres >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done

  if ! compose exec -T postgres pg_isready -U postgres -d postgres >/dev/null 2>&1; then
    echo "PostgreSQL did not become ready in time." >&2
    exit 1
  fi

  DUMP_IN_CONTAINER="/tmp/planka-restore.dump"
  echo "Copying database dump into PostgreSQL container..."
  docker cp "${BACKUP_DIR}/postgres.dump" "${POSTGRES_CONTAINER}:${DUMP_IN_CONTAINER}"

  echo "Restoring PostgreSQL database..."
  compose exec -T postgres psql -U postgres -d postgres -v ON_ERROR_STOP=1 <<'SQL'
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'planka' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS planka;
CREATE DATABASE planka;
SQL
  compose exec -T postgres pg_restore -U postgres -d planka --clean --if-exists "${DUMP_IN_CONTAINER}"
  compose exec -T postgres rm -f "${DUMP_IN_CONTAINER}"
fi

if [ "${SKIP_DATA}" -eq 0 ]; then
  PROJECT_NAME="$(basename "${PLANKA_DIR}" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '_')"
  DATA_VOLUME="${PROJECT_NAME}_planka-data"

  if ! docker volume inspect "${DATA_VOLUME}" >/dev/null 2>&1; then
    echo "Creating PLANKA data volume: ${DATA_VOLUME}"
    docker volume create "${DATA_VOLUME}" >/dev/null
  fi

  echo "Restoring PLANKA data volume..."
  docker run --rm \
    -v "${DATA_VOLUME}:/data" \
    -v "${BACKUP_DIR}:/backup:ro" \
    alpine:3.20 \
    sh -c 'rm -rf /data/* /data/.[!.]* /data/..?* 2>/dev/null || true; cd /data && tar -xzf /backup/planka-data.tar.gz'
fi

echo "Starting PLANKA stack..."
compose up -d

echo "Restore complete."
