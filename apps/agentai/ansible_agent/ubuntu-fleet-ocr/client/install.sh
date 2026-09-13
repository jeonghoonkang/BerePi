#!/usr/bin/env bash
# Copy client/ (including register_device.py) and a device.env file to the device.
set -euo pipefail
umask 077

usage() {
  echo "Usage: sudo bash $0 [/root/sononet-device.env] [--device-id ID | --server-id]"
  echo "Downloads fleet-ocr from BerePi/master, installs it, and starts OCR."
  echo "기본은 클라이언트 ID 직접 입력입니다. 서버에서 할당받으려면 --server-id를 사용하세요."
}

requested_id=
server_id=0
source_file=
while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --device-id)
      if [[ $# -lt 2 || -z $2 ]]; then usage >&2; exit 2; fi
      requested_id=$2; shift 2 ;;
    --server-id) server_id=1; shift ;;
    -*) usage >&2; exit 2 ;;
    *)
      if [[ -n ${source_file} ]]; then usage >&2; exit 2; fi
      source_file=$1; shift ;;
  esac
done
if [[ ${server_id} == 1 && -n ${requested_id} ]]; then
  echo "Choose --device-id or --server-id, not both." >&2
  exit 2
fi
if [[ ${EUID} -ne 0 ]]; then
  echo "Run this installer with sudo on the Ubuntu client." >&2
  exit 1
fi
if [[ ! -f /etc/os-release ]]; then
  echo "This installer requires Ubuntu/Debian with systemd." >&2
  exit 1
fi
# shellcheck disable=SC1091
source /etc/os-release
if [[ ${ID:-} != ubuntu && ${ID:-} != debian ]]; then
  echo "This installer requires Ubuntu/Debian with systemd." >&2
  exit 1
fi
if [[ ! -d /run/systemd/system ]]; then
  echo "Boot the client with systemd before running this installer." >&2
  exit 1
fi

source_file=${source_file:-/root/sononet-device.env}
if [[ ! -f ${source_file} ]]; then
  echo "Device configuration not found: ${source_file}" >&2
  echo "Fill in client/device.env.example and save it here with mode 0600." >&2
  exit 2
fi

# This is a trusted administrator-provided shell environment file.
set -a
# shellcheck disable=SC1090
source "${source_file}"
set +a
export SONONET_REPO_URL=${SONONET_REPO_URL:-https://github.com/jeonghoonkang/BerePi.git}
export SONONET_REPO_BRANCH=${SONONET_REPO_BRANCH:-master}
export SONONET_PLAYBOOK_PATH=${SONONET_PLAYBOOK_PATH:-apps/agentai/ansible_agent/ubuntu-fleet-ocr/local.yml}
export SONONET_VERIFY_COMMIT=${SONONET_VERIFY_COMMIT:-0}
export SONONET_ID_MODE=${SONONET_ID_MODE:-manual}
export SONONET_FETCH_DEVICE_TOKEN=${SONONET_FETCH_DEVICE_TOKEN:-0}
export DEVICE_TOKEN=${DEVICE_TOKEN:-}
export FLEET_API_URL=${FLEET_API_URL:-}
export FLEET_ID_API_URL=${FLEET_ID_API_URL:-${FLEET_API_URL:-}}
export FLEET_ID_REGISTER_PATH=${FLEET_ID_REGISTER_PATH:-/v1/devices/register}
export FLEET_ID_MANUAL_PATH=${FLEET_ID_MANUAL_PATH:-/v1/devices/manual}
if [[ -n ${requested_id} ]]; then
  SONONET_ID_MODE=manual
  if [[ ${SONONET_DEVICE_ID:-} != "${requested_id}" ]]; then
    export DEVICE_TOKEN=
  fi
  export SONONET_DEVICE_ID=${requested_id}
fi
if [[ ${server_id} == 1 ]]; then
  SONONET_ID_MODE=auto
  export SONONET_DEVICE_ID=
  DEVICE_TOKEN=
fi
if [[ ${SONONET_FETCH_DEVICE_TOKEN} != 0 && ${SONONET_FETCH_DEVICE_TOKEN} != 1 ]]; then
  echo "SONONET_FETCH_DEVICE_TOKEN must be 0 or 1." >&2
  exit 3
fi
if [[ ${SONONET_ID_MODE} != auto && ${SONONET_ID_MODE} != manual ]]; then
  echo "SONONET_ID_MODE must be auto or manual." >&2
  exit 3
fi
if [[ ${SONONET_ID_MODE} == manual ]]; then
  echo "클라이언트에서 ID를 직접 설정합니다. ID 설정 서버에는 기본적으로 연결하지 않습니다."
  echo "서버에서 ID를 할당받을 수도 있습니다: --server-id (서버 주소와 FLEET_ENROLLMENT_TOKEN 설정 필요)."
  if [[ -z ${SONONET_DEVICE_ID:-} && -t 0 ]]; then
    read -r -p "Device ID: " SONONET_DEVICE_ID
    export SONONET_DEVICE_ID
  fi
  if [[ ! ${SONONET_DEVICE_ID:-} =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ||
        ${#SONONET_DEVICE_ID} -gt 128 || ${SONONET_DEVICE_ID} == CHANGE_ME ]]; then
    echo "Enter a device ID (1-128 letters/digits/dot/underscore/hyphen; start with letter/digit)." >&2
    exit 3
  fi
fi

required=(
  NEXTCLOUD_URL NEXTCLOUD_USER NEXTCLOUD_APP_PASSWORD OCR_API_BASE_URL
)
for name in "${required[@]}"; do
  if [[ -z ${!name:-} || ${!name} == CHANGE_ME ]]; then
    echo "Fill in device configuration: ${name}" >&2
    exit 3
  fi
done
# Keep explicitly provisioned legacy devices working. New devices leave both blank.
request_identity=0
export FLEET_ENROLLMENT_TOKEN=${FLEET_ENROLLMENT_TOKEN:-}
if [[ -z ${DEVICE_TOKEN} && ( ${SONONET_ID_MODE} == auto || ${SONONET_FETCH_DEVICE_TOKEN} == 1 ) ]]; then
  request_identity=1
  if [[ ${#FLEET_ENROLLMENT_TOKEN} -lt 32 || ${FLEET_ENROLLMENT_TOKEN} == CHANGE_ME* ]]; then
    echo "Set FLEET_ENROLLMENT_TOKEN to obtain a device authentication token." >&2
    exit 3
  fi
  script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
  if [[ ! -f ${script_dir}/register_device.py ]]; then
    echo "Copy register_device.py alongside install.sh." >&2
    exit 3
  fi
elif [[ -z ${SONONET_DEVICE_ID:-} || ( ${SONONET_ID_MODE} == auto && -z ${DEVICE_TOKEN} ) ||
        ${SONONET_DEVICE_ID:-} == CHANGE_ME || ${DEVICE_TOKEN:-} == CHANGE_ME ]]; then
  echo "Use an empty DEVICE_TOKEN in manual mode, or leave both ID and token empty in auto mode." >&2
  exit 3
fi
if [[ ${request_identity} == 1 && -z ${FLEET_ID_API_URL} ]]; then
  echo "Set FLEET_ID_API_URL (or FLEET_API_URL) for the selected server request." >&2
  exit 3
fi
if [[ ${SONONET_ID_MODE} == manual && -z ${DEVICE_TOKEN} && ${request_identity} == 0 ]]; then
  echo "로컬 ID를 저장합니다. 서버 상태 보고·충돌 확인은 DEVICE_TOKEN과 FLEET_API_URL 설정 후 사용할 수 있습니다."
  echo "입력한 ID의 인증 토큰만 요청하려면 SONONET_FETCH_DEVICE_TOKEN=1을 설정하세요."
fi
if [[ ${OCR_API_KEY:-} == CHANGE_ME ]]; then
  echo "Set OCR_API_KEY, or leave it empty only for an OCR server without authentication." >&2
  exit 3
fi
if [[ ! ${SONONET_PLAYBOOK_PATH} =~ ^[a-zA-Z0-9_./-]+$ ||
      ${SONONET_PLAYBOOK_PATH} == /* ||
      ${SONONET_PLAYBOOK_PATH} == -* ||
      /${SONONET_PLAYBOOK_PATH}/ == */../* ]]; then
  echo "SONONET_PLAYBOOK_PATH must be a relative path inside the Git repository." >&2
  exit 3
fi

# Share the lock with the periodic updater so installation cannot overlap it.
exec 9>/run/lock/sononet-ansible-pull.lock
if ! flock -n 9; then
  echo "Another fleet-ocr installation or update is running. Retry later." >&2
  exit 4
fi

install -d -m 0750 /etc/sononet
# Stage first so /etc/sononet/device.env itself can also be used as input.
config_tmp=$(mktemp /etc/sononet/device.env.XXXXXX)
trap 'rm -f -- "${config_tmp}"' EXIT
install -m 0600 -o root -g root "${source_file}" "${config_tmp}"
# Persist resolved defaults for updates after reboot. %q escapes shell values.
{
  printf '\n# Download settings resolved by the client installer.\n'
  printf 'SONONET_REPO_URL=%q\n' "${SONONET_REPO_URL}"
  printf 'SONONET_REPO_BRANCH=%q\n' "${SONONET_REPO_BRANCH}"
  printf 'SONONET_PLAYBOOK_PATH=%q\n' "${SONONET_PLAYBOOK_PATH}"
  printf 'SONONET_VERIFY_COMMIT=%q\n' "${SONONET_VERIFY_COMMIT}"
  printf 'SONONET_ID_MODE=%q\n' "${SONONET_ID_MODE}"
  printf 'SONONET_FETCH_DEVICE_TOKEN=%q\n' "${SONONET_FETCH_DEVICE_TOKEN}"
  printf 'SONONET_DEVICE_ID=%q\n' "${SONONET_DEVICE_ID:-}"
  printf 'DEVICE_TOKEN=%q\n' "${DEVICE_TOKEN:-}"
  printf 'FLEET_ID_API_URL=%q\n' "${FLEET_ID_API_URL}"
  printf 'FLEET_ID_REGISTER_PATH=%q\n' "${FLEET_ID_REGISTER_PATH}"
  printf 'FLEET_ID_MANUAL_PATH=%q\n' "${FLEET_ID_MANUAL_PATH}"
} >> "${config_tmp}"

export DEBIAN_FRONTEND=noninteractive
apt-get -o Acquire::Retries=3 update
apt-get -o Acquire::Retries=3 install -y --no-install-recommends ansible-core git ca-certificates python3

if [[ ${request_identity} == 1 ]]; then
  if [[ ${SONONET_ID_MODE} == manual ]]; then
    echo "Using manually entered ID: ${SONONET_DEVICE_ID}; requesting authentication only."
  else
    echo "Requesting a unique device number from the Fleet server..."
  fi
  # The helper persists its retry key before the request. No token is printed to the terminal.
  python3 "${script_dir}/register_device.py" /etc/sononet/registration.json >> "${config_tmp}"
fi
set -a
# shellcheck disable=SC1090
source "${config_tmp}"
set +a
export NEXTCLOUD_REMOTE_PATH=${NEXTCLOUD_REMOTE_PATH:-/Fleet/${SONONET_DEVICE_ID}}
printf 'NEXTCLOUD_REMOTE_PATH=%q\n' "${NEXTCLOUD_REMOTE_PATH}" >> "${config_tmp}"
mv -f -- "${config_tmp}" /etc/sononet/device.env
echo "Device number: ${SONONET_DEVICE_ID}; Nextcloud folder: ${NEXTCLOUD_REMOTE_PATH}"

pull_args=(
  -U "${SONONET_REPO_URL}"
  -C "${SONONET_REPO_BRANCH}"
  -d /var/lib/sononet/ansible
  -i localhost,
  -c local
  --clean
  "${SONONET_PLAYBOOK_PATH}"
)
if [[ ${SONONET_VERIFY_COMMIT} == 1 ]]; then
  pull_args=(--verify-commit "${pull_args[@]}")
fi
echo "Downloading and installing fleet-ocr from ${SONONET_REPO_URL} (${SONONET_REPO_BRANCH})..."
ansible-pull "${pull_args[@]}"

# The playbook enables persistent timers; also run the first pipeline immediately.
systemctl start sononet-pipeline.service
systemctl start sononet-heartbeat.service
echo "fleet-ocr installed and first run completed for ${SONONET_DEVICE_ID}."
echo "After reboot, OCR, heartbeat, and updates run automatically via sononet-* timers."
