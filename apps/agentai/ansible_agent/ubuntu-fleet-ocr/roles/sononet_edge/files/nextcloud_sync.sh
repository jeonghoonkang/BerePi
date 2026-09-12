#!/usr/bin/env bash
set -euo pipefail

: "${SONONET_DEVICE_ID:?SONONET_DEVICE_ID is required}"
: "${NEXTCLOUD_URL:?NEXTCLOUD_URL is required}"
: "${NEXTCLOUD_USER:?NEXTCLOUD_USER is required}"
: "${NEXTCLOUD_APP_PASSWORD:?NEXTCLOUD_APP_PASSWORD is required}"

local_dir=${NEXTCLOUD_LOCAL_DIR:-/var/lib/sononet/sync}
remote_path=${NEXTCLOUD_REMOTE_PATH:-/Fleet/${SONONET_DEVICE_ID}}

install -d -m 0750 "${local_dir}/inbox" "${local_dir}/ocr-results"
export NC_USER=${NEXTCLOUD_USER}
export NC_PASSWORD=${NEXTCLOUD_APP_PASSWORD}

echo "event=nextcloud_sync_start device_id=${SONONET_DEVICE_ID} remote_path=${remote_path}"
/usr/bin/nextcloudcmd \
  --non-interactive \
  --max-sync-retries 3 \
  --path "${remote_path}" \
  "${local_dir}" \
  "${NEXTCLOUD_URL}"
echo "event=nextcloud_sync_complete device_id=${SONONET_DEVICE_ID}"

