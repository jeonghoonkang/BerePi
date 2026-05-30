#!/usr/bin/env bash
set -u

SOURCE_PATH="${1:-}"
RECENT_DIR="${MOTION_RECENT_DIR:-/var/lib/motion_recent}"

log() {
    printf '%s\n' "$*" >&2
}

if [ -z "$SOURCE_PATH" ]; then
    log "usage: $0 /path/to/motion-image"
    exit 2
fi

if [ ! -f "$SOURCE_PATH" ]; then
    log "motion source file not found: $SOURCE_PATH"
    exit 0
fi

case "${SOURCE_PATH##*.}" in
    jpg|JPG|jpeg|JPEG|png|PNG|webp|WEBP) ;;
    *) exit 0 ;;
esac

mkdir -p "$RECENT_DIR"

base_name="$(basename "$SOURCE_PATH")"
target_path="$RECENT_DIR/$base_name"

if [ -e "$target_path" ] && [ "$SOURCE_PATH" -ef "$target_path" ]; then
    exit 0
fi

if [ -e "$target_path" ]; then
    stem="${base_name%.*}"
    ext="${base_name##*.}"
    target_path="$RECENT_DIR/${stem}_$(date +%Y%m%d%H%M%S)_$$.${ext}"
fi

if ln "$SOURCE_PATH" "$target_path" 2>/dev/null; then
    exit 0
fi

log "hardlink failed; falling back to symlink: $SOURCE_PATH -> $target_path"
ln -s "$SOURCE_PATH" "$target_path"
