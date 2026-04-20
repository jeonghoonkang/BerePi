#!/bin/bash
# Author: github.com/jeonghoonkang

set -euo pipefail

show_help() {
  cat <<'EOF'
Usage:
  ./delete_old_files.sh [target_dir] [days] [pattern] [--delete]

Description:
  Finds files older than the given number of days and prints them.
  Use --delete to actually remove the files.

Arguments:
  target_dir   Directory to scan. Default: .
  days         Delete files older than this many days. Default: 30
  pattern      File name pattern for find -name. Default: *

Options:
  --delete     Actually delete files
  -h, --help   Show this help message

Examples:
  ./delete_old_files.sh
  ./delete_old_files.sh /var/log 14 "*.log"
  ./delete_old_files.sh /data/images 7 "*.jpg" --delete
EOF
}

TARGET_DIR="."
DAYS="30"
PATTERN="*"
DELETE_MODE="false"

POSITIONAL_ARGS=()

for arg in "$@"; do
  case "$arg" in
    --delete)
      DELETE_MODE="true"
      ;;
    -h|--help)
      show_help
      exit 0
      ;;
    *)
      POSITIONAL_ARGS+=("$arg")
      ;;
  esac
done

if [ "${#POSITIONAL_ARGS[@]}" -ge 1 ]; then
  TARGET_DIR="${POSITIONAL_ARGS[0]}"
fi

if [ "${#POSITIONAL_ARGS[@]}" -ge 2 ]; then
  DAYS="${POSITIONAL_ARGS[1]}"
fi

if [ "${#POSITIONAL_ARGS[@]}" -ge 3 ]; then
  PATTERN="${POSITIONAL_ARGS[2]}"
fi

if ! [[ "$DAYS" =~ ^[0-9]+$ ]]; then
  echo "Error: days must be a non-negative integer." >&2
  exit 1
fi

if [ ! -d "$TARGET_DIR" ]; then
  echo "Error: target directory not found: $TARGET_DIR" >&2
  exit 1
fi

echo "Target directory : $TARGET_DIR"
echo "Older than days  : $DAYS"
echo "File pattern     : $PATTERN"

if [ "$DELETE_MODE" = "true" ]; then
  echo "Mode             : delete"
  find "$TARGET_DIR" -type f -name "$PATTERN" -mtime +"$DAYS" -print -delete
else
  echo "Mode             : dry-run"
  find "$TARGET_DIR" -type f -name "$PATTERN" -mtime +"$DAYS" -print
  echo
  echo "No files were deleted."
  echo "Add --delete to remove the listed files."
fi
