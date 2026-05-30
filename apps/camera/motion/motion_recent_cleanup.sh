#!/usr/bin/env bash
set -u

RECENT_DIR="${1:-${MOTION_RECENT_DIR:-/var/lib/motion_recent}}"
KEEP_MINUTES="${2:-1440}"

if [ ! -d "$RECENT_DIR" ]; then
    exit 0
fi

find "$RECENT_DIR" -mindepth 1 -maxdepth 1 \( -type f -o -type l \) -mmin +"$KEEP_MINUTES" -delete
