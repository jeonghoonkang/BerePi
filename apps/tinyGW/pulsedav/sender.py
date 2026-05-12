from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pulsedav import (
    DEFAULT_INTERVAL_MINUTES,
    WebDAVConnectionError,
    load_settings,
    resolve_settings_path,
    run_loop,
    send_once,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send system status markdown to WebDAV.")
    parser.add_argument("--once", action="store_true", help="Send one report and exit.")
    parser.add_argument("--loop", action="store_true", help="Run continuously using the configured interval.")
    parser.add_argument("--interval-minutes", type=int, help="Override interval for loop mode.")
    parser.add_argument(
        "--config",
        help="Path to a settings JSON file. Defaults to apps/tinyGW/pulsedav/settings.json",
    )
    parser.add_argument(
        "--print-crontab",
        action="store_true",
        help="Print cron lines that can be added to crontab and exit.",
    )
    return parser.parse_args()


def build_crontab_lines(config_path: str | None, interval_minutes: int | None) -> list[str]:
    """Build example crontab lines for the current CLI configuration."""
    app_dir = Path(__file__).resolve().parent
    python_bin = sys.executable or "/usr/bin/python3"
    resolved_config_path = resolve_settings_path(config_path)
    config_args = f" --config {resolved_config_path}" if config_path else ""

    settings = load_settings(config_path)
    configured_interval = int(
        interval_minutes
        or settings.get("schedule", {}).get("interval_minutes", DEFAULT_INTERVAL_MINUTES)
        or DEFAULT_INTERVAL_MINUTES
    )
    cron_interval = max(1, min(configured_interval, 59))

    base_command = f"{python_bin} sender.py --once{config_args}"
    return [
        f"@reboot cd {app_dir} && {base_command} > pulsedav.log 2>&1",
        f"*/{cron_interval} * * * * cd {app_dir} && {base_command} > pulsedav.log 2>&1",
    ]


def main() -> int:
    args = parse_args()
    if args.print_crontab:
        print("\n".join(build_crontab_lines(args.config, args.interval_minutes)))
        return 0

    if args.loop:
        run_loop(args.interval_minutes, settings_path=args.config)
        return 0

    try:
        send_once(load_settings(args.config), settings_path=args.config)
    except WebDAVConnectionError as exc:
        print(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
