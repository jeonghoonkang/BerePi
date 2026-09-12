#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root: sudo bash $0 /path/to/device.env" >&2
  exit 1
fi

source_file=${1:-}
if [[ -z ${source_file} || ! -f ${source_file} ]]; then
  echo "Usage: sudo bash $0 /root/sononet-device.env" >&2
  exit 2
fi

install -d -m 0750 /etc/sononet
install -m 0600 -o root -g root "${source_file}" /etc/sononet/device.env

# shellcheck disable=SC1091
set -a
source /etc/sononet/device.env
set +a

required=(
  SONONET_DEVICE_ID SONONET_REPO_URL NEXTCLOUD_URL NEXTCLOUD_USER
  NEXTCLOUD_APP_PASSWORD OCR_API_BASE_URL FLEET_API_URL DEVICE_TOKEN
)
for name in "${required[@]}"; do
  if [[ -z ${!name:-} || ${!name} == CHANGE_ME ]]; then
    echo "Missing or unsafe value: ${name}" >&2
    exit 3
  fi
done

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ansible-core git ca-certificates

pull_args=(
  -U "${SONONET_REPO_URL}"
  -C "${SONONET_REPO_BRANCH:-stable}"
  -d /var/lib/sononet/ansible
  -i localhost,
  -c local
  --clean
  local.yml
)

if [[ ${SONONET_VERIFY_COMMIT:-0} == 1 ]]; then
  pull_args=(--verify-commit "${pull_args[@]}")
fi

ansible-pull "${pull_args[@]}"
echo "Sononet edge installation completed for ${SONONET_DEVICE_ID}."
