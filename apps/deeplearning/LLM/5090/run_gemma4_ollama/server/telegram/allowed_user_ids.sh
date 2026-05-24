#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IDS_FILE="${ALLOWED_TELEGRAM_USER_IDS_FILE:-${APP_DIR}/allowed_telegram_user_ids.txt}"

usage() {
  printf 'Usage:\n'
  printf '  %s add USER_ID\n' "$0"
  printf '  %s delete USER_ID\n' "$0"
  printf '  %s remove USER_ID\n' "$0"
  printf '  %s list\n' "$0"
  printf '  %s export\n' "$0"
}

ensure_file() {
  if [[ ! -f "${IDS_FILE}" ]]; then
    {
      printf '# One Telegram numeric user ID per line.\n'
      printf '# Use ./allowed_user_ids.sh add 123456789 to add an ID.\n'
    } > "${IDS_FILE}"
  fi
}

validate_user_id() {
  local user_id="$1"
  if [[ ! "${user_id}" =~ ^[0-9]+$ ]]; then
    printf 'USER_ID must be a numeric Telegram user ID: %s\n' "${user_id}" >&2
    exit 1
  fi
}

read_ids() {
  ensure_file
  awk '
    {
      sub(/#.*/, "")
      gsub(/^[[:space:]]+|[[:space:]]+$/, "")
      if ($0 != "") print $0
    }
  ' "${IDS_FILE}" | sort -u
}

write_ids() {
  local temp_file
  temp_file="$(mktemp)"
  {
    printf '# One Telegram numeric user ID per line.\n'
    printf '# Managed by allowed_user_ids.sh.\n'
    sort -u
  } > "${temp_file}"
  mv "${temp_file}" "${IDS_FILE}"
}

add_id() {
  local user_id="$1"
  validate_user_id "${user_id}"
  {
    read_ids
    printf '%s\n' "${user_id}"
  } | write_ids
  printf 'Added Telegram user ID: %s\n' "${user_id}"
}

delete_id() {
  local user_id="$1"
  validate_user_id "${user_id}"
  read_ids | awk -v id="${user_id}" '$0 != id' | write_ids
  printf 'Deleted Telegram user ID: %s\n' "${user_id}"
}

list_ids() {
  read_ids
}

export_ids() {
  local joined
  joined="$(read_ids | paste -sd, -)"
  printf 'export ALLOWED_TELEGRAM_USER_IDS="%s"\n' "${joined}"
}

command="${1:-}"
case "${command}" in
  add)
    [[ $# -eq 2 ]] || { usage >&2; exit 1; }
    add_id "$2"
    ;;
  delete|remove)
    [[ $# -eq 2 ]] || { usage >&2; exit 1; }
    delete_id "$2"
    ;;
  list)
    [[ $# -eq 1 ]] || { usage >&2; exit 1; }
    list_ids
    ;;
  export)
    [[ $# -eq 1 ]] || { usage >&2; exit 1; }
    export_ids
    ;;
  *)
    usage >&2
    exit 1
    ;;
esac
