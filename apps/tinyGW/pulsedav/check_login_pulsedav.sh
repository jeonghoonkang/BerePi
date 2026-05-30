#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MESSAGE="Missing PulseDAV"

cron_has_pulsedav() {
    awk -v app_dir="$SCRIPT_DIR" '
        /^[[:space:]]*($|#)/ { next }
        index($0, app_dir) > 0 && index($0, "sender.py") > 0 { found = 1 }
        index($0, "pulsedav") > 0 && index($0, "sender.py") > 0 { found = 1 }
        END { exit found ? 0 : 1 }
    '
}

user_crontab_has_pulsedav() {
    crontab -l 2>/dev/null | cron_has_pulsedav
}

root_crontab_has_pulsedav() {
    command -v sudo >/dev/null 2>&1 || return 1
    sudo -n crontab -l 2>/dev/null | cron_has_pulsedav
}

main() {
    if ! command -v crontab >/dev/null 2>&1; then
        echo "$MESSAGE"
        return 0
    fi

    if user_crontab_has_pulsedav || root_crontab_has_pulsedav; then
        return 0
    fi

    echo "$MESSAGE"
}

main "$@"
