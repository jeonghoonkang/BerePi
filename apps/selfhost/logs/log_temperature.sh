#!/bin/sh

set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
LOG_FILE="$SCRIPT_DIR/log_temperaure.txt"
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
  echo "$TIMESTAMP ERROR temperature_unavailable" >> "$LOG_FILE"
else
  echo "$TIMESTAMP ${TEMPERATURE}C" >> "$LOG_FILE"
fi

LINE_COUNT="$(wc -l < "$LOG_FILE" | tr -d ' ')"
if [ "$LINE_COUNT" -gt "$MAX_LINES" ]; then
  TMP_FILE="$SCRIPT_DIR/.log_temperaure.txt.tmp"
  tail -n "$MAX_LINES" "$LOG_FILE" > "$TMP_FILE"
  mv "$TMP_FILE" "$LOG_FILE"
fi
