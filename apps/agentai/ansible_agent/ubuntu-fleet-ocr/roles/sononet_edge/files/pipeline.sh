#!/usr/bin/env bash
set -uo pipefail

app_dir=/usr/local/lib/sononet
report_event() {
  /usr/bin/python3 "${app_dir}/report_event.py" "$@" >/dev/null 2>&1 || true
}

echo "event=pipeline_start device_id=${SONONET_DEVICE_ID:-unknown}"
report_event pipeline_start info "Nextcloud OCR pipeline started"

if ! "${app_dir}/nextcloud_sync.sh"; then
  echo "event=pipeline_failed stage=download_sync" >&2
  report_event pipeline_failed error "Initial Nextcloud synchronization failed"
  exit 20
fi

if ! /usr/bin/python3 "${app_dir}/ocr_worker.py"; then
  echo "event=pipeline_failed stage=ocr" >&2
  report_event pipeline_failed error "Gemma OCR stage failed"
  exit 30
fi

if ! "${app_dir}/nextcloud_sync.sh"; then
  echo "event=pipeline_failed stage=result_upload" >&2
  report_event pipeline_failed error "OCR result synchronization failed"
  exit 40
fi

echo "event=pipeline_complete device_id=${SONONET_DEVICE_ID:-unknown}"
report_event pipeline_complete info "Nextcloud OCR pipeline completed"
