#!/usr/bin/env bash
set -eo pipefail

BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${TELEGRAM_CONFIG_FILE:-${BOT_DIR}/this_conf_keys.sh}"
# Legacy config files reference unset positional parameters; do not enable nounset.
if [[ -f "${CONFIG_FILE}" ]]; then
  source "${CONFIG_FILE}" set
elif [[ -n "${TELEGRAM_CONFIG_FILE:-}" ]]; then
  echo "Telegram config file not found: ${CONFIG_FILE}" >&2
  exit 1
fi
if [[ -z "${TELEGRAM_BOT_TOKEN:-}" || "${TELEGRAM_BOT_TOKEN}" == '***' ]]; then
  echo "Telegram skipped: set TELEGRAM_BOT_TOKEN or configure telegram/this_conf_keys.sh."
  exit 0
fi
export LLM_API_URL="${LLM_API_URL:-http://127.0.0.1:${GEMMA4_SERVER_PORT:-8082}/api/generate}"
if [[ -z "${TELEGRAM_PYTHON:-}" ]]; then
  if [[ -x "${BOT_DIR}/.venv/bin/python" ]]; then
    TELEGRAM_PYTHON="${BOT_DIR}/.venv/bin/python"
  elif [[ -x "${BOT_DIR}/install/bin/python" ]]; then
    TELEGRAM_PYTHON="${BOT_DIR}/install/bin/python"
  else
    TELEGRAM_PYTHON="$(command -v python3)"
  fi
fi
cd "${BOT_DIR}"
# Keep a process-owned lock across exec. Released automatically on shutdown.
# All managed instances use the same lock to avoid duplicate polling.
if ! command -v flock >/dev/null 2>&1; then
  echo "Telegram requires flock (util-linux) for duplicate-start protection." >&2
  exit 1
fi
mkdir -p logs
exec 9>logs/bot.lock
if ! flock -n 9; then
  echo "Telegram skipped: another managed bot is already running."
  exit 0
fi
echo "Starting Telegram bot; API=${LLM_API_URL}"
exec "${TELEGRAM_PYTHON}" -u "${BOT_DIR}/bot.py"
