#!/bin/sh

set -eu

if [ "$(id -u)" -ne 0 ]; then
  echo "This script must be run as root." >&2
  exit 1
fi

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
LOG_FILE="$SCRIPT_DIR/log_temperature.txt"
MAX_LINES=500

read_temp_celsius() {
  if command -v vcgencmd >/dev/null 2>&1; then
    vcgencmd measure_temp | sed -E "s/^temp=([0-9.]+).*/\1/"
    return 0
  fi

  if [ -r /sys/class/thermal/thermal_zone0/temp ]; then
    awk '{ printf "%.1f", $1 / 1000 }' /sys/class/thermal/thermal_zone0/temp
    return 0
  fi

  return 1
}

TEMPERATURE="$(read_temp_celsius || true)"
TIMESTAMP="$(date "+%Y-%m-%d %H:%M:%S")"

if [ -z "$TEMPERATURE" ]; then
  LOG_MESSAGE="$TIMESTAMP ERROR temperature_unavailable"
else
  LOG_MESSAGE="$TIMESTAMP ${TEMPERATURE}C"
fi

printf '%s\n' "$LOG_MESSAGE" | tee -a "$LOG_FILE"

LINE_COUNT="$(wc -l < "$LOG_FILE" | tr -d ' ')"
if [ "$LINE_COUNT" -gt "$MAX_LINES" ]; then
  TMP_FILE="$SCRIPT_DIR/.log_temperaure.txt.tmp"
  tail -n "$MAX_LINES" "$LOG_FILE" > "$TMP_FILE"
  mv "$TMP_FILE" "$LOG_FILE"
fi
