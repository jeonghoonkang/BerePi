from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from pulsedav import (
    DEFAULT_INTERVAL_MINUTES,
    WebDAVConnectionError,
    load_settings,
    resolve_settings_path,
    run_loop,
    send_iptime_list,
    send_once,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send system status markdown to WebDAV.")
    parser.add_argument("--once", action="store_true", help="Send one report and exit.")
    parser.add_argument("--reboot", action="store_true", help="Mark this one-shot send as a reboot-time run.")
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
    parser.add_argument(
        "--iptime-list",
        action="store_true",
        help="Send ipTIME ping status and device list to WebDAV before the normal PulseDAV report.",
    )
    return parser.parse_args()


def current_time_text() -> str:
    now = datetime.now().astimezone()
    return f"{now.year:04d}-{now.month:02d}-{now.day:02d} {now.hour:02d}:{now.minute:02d}:{now.second:02d} {now.tzname()}"


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

    timestamp_command = (
        f"{python_bin} -c 'from datetime import datetime; "
        'd=datetime.now().astimezone(); '
        'print(f"{d.year:04d}-{d.month:02d}-{d.day:02d} '
        '{d.hour:02d}:{d.minute:02d}:{d.second:02d} {d.tzname()}")\''
    )
    reboot_command = f"{python_bin} sender.py --once --reboot{config_args}"
    base_command = f"{python_bin} sender.py --once{config_args}"
    reboot_log_command = f"{{ echo 'reboot 시점'; {timestamp_command}; {reboot_command}; }} > pulsedav.log 2>&1"
    log_command = f"{{ {timestamp_command}; {base_command}; }} > pulsedav.log 2>&1"
    return [
        f"@reboot cd {app_dir} && {reboot_log_command}",
        f"*/{cron_interval} * * * * cd {app_dir} && {log_command}",
    ]


def main() -> int:
    args = parse_args()
    settings = load_settings(args.config)
    if args.print_crontab:
        print("\n".join(build_crontab_lines(args.config, args.interval_minutes)))
        return 0

    if args.iptime_list:
        try:
            result = send_iptime_list(settings, settings_path=args.config)
        except WebDAVConnectionError as exc:
            print(str(exc))
            return 1
        print(result["preview"])
        print()
        print("ipTIME 목록 WebDAV 전송 완료")
        print(f"- 호스트명: {result['host_name']}")
        print(f"- 파일명: {result['file_name']}")
        print(f"- 전송 주소: {result['webdav_hostname']}")
        print(f"- WebDAV 루트: {result['webdav_root']}")
        print(f"- WebDAV 서브: {result['webdav_sub']}")
        print(f"- 저장 디렉토리: {result['remote_directory']}")
        print(f"- 저장 경로: {result['remote_path']}")
        print(f"- 전체 URL: {result['destination_url']}")
        print()

    if args.loop:
        run_loop(args.interval_minutes, settings_path=args.config)
        return 0

    if args.reboot:
        print(f"reboot 시점: {current_time_text()}")

    try:
        result = send_once(settings, settings_path=args.config, reboot_run=args.reboot)
    except WebDAVConnectionError as exc:
        print(str(exc))
        return 1
    print("PulseDAV 전송 완료")
    if args.reboot:
        print("- 실행 구분: reboot 시점")
    print(f"- 호스트명: {result['host_name']}")
    print(f"- 파일명: {result['file_name']}")
    print(f"- 전송 주소: {result['webdav_hostname']}")
    print(f"- WebDAV 루트: {result['webdav_root']}")
    print(f"- WebDAV 서브: {result['webdav_sub']}")
    print(f"- 저장 디렉토리: {result['remote_directory']}")
    print(f"- 저장 경로: {result['remote_path']}")
    print(f"- 전체 URL: {result['destination_url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
