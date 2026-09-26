from __future__ import annotations

import argparse
import os
import platform
import shlex
import subprocess
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
    parser.add_argument("--gateway-watchdog", action="store_true", help="Check the Linux default gateway; reboot after 30 minutes of continuous ping failure.")
    parser.add_argument("--gateway-dry-run", action="store_true", help="Check normally but never reboot (requires --gateway-watchdog).")
    parser.add_argument("--install-crontab", action="store_true", help="Replace this installation's matching cron jobs with the current arguments.")
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
    status_modes = parser.add_mutually_exclusive_group()
    status_modes.add_argument('--check-status', action='store_true', help='Check only this machine’s configured WebDAV upload directories.')
    status_modes.add_argument('--check-status-all', action='store_true', help='Check all nodes recursively under /tinyGW.')
    parser.add_argument('--server-list', help='Optional JSON server inventory with server_name, ip_address, open_port, directory.')
    parser.add_argument('--status-output-dir', help='Directory for server_status.json and server_status.txt.')
    parser.add_argument('--max-age-minutes', type=int, help='Stale recording threshold (default: twice configured interval).')
    args = parser.parse_args()
    if (args.check_status or args.check_status_all) and any((args.once, args.loop, args.reboot, args.iptime_list, args.print_crontab, args.install_crontab, args.gateway_watchdog, args.gateway_dry_run)):
        parser.error('status checks cannot be combined with send or crontab modes')
    if args.gateway_dry_run and not args.gateway_watchdog:
        parser.error("--gateway-dry-run requires --gateway-watchdog")
    if args.gateway_watchdog and (args.once or args.loop or args.reboot or args.iptime_list):
        parser.error("--gateway-watchdog runs separately from report sending options")
    if args.print_crontab and args.install_crontab:
        parser.error("choose --print-crontab or --install-crontab")
    return args


def current_time_text() -> str:
    now = datetime.now().astimezone()
    return f"{now.year:04d}-{now.month:02d}-{now.day:02d} {now.hour:02d}:{now.minute:02d}:{now.second:02d} {now.tzname()}"


def print_upload_targets(result: dict[str, object]) -> None:
    remote_paths = result.get("remote_paths")
    destination_urls = result.get("destination_urls")
    if not isinstance(remote_paths, list) or len(remote_paths) <= 1:
        return

    print(f"- 업로드 개수: {len(remote_paths)}")
    print("- 전체 저장 경로:")
    for remote_path in remote_paths:
        print(f"  - {remote_path}")
    if isinstance(destination_urls, list):
        print("- 전체 URL 목록:")
        for destination_url in destination_urls:
            print(f"  - {destination_url}")


def build_crontab_lines(config_path: str | None, interval_minutes: int | None,
                        gateway_watchdog: bool = False, gateway_dry_run: bool = False) -> list[str]:
    """Build example crontab lines for the current CLI configuration."""
    app_dir = shlex.quote(str(Path(__file__).resolve().parent))
    python_bin = shlex.quote(sys.executable or "/usr/bin/python3")
    if gateway_watchdog:
        command = f"cd {app_dir} && {python_bin} sender.py --gateway-watchdog"
        if gateway_dry_run:
            command += " --gateway-dry-run"
        command += " > gateway-watchdog.log 2>&1"
        return [f"{schedule} {command}".replace("%", r"\%") for schedule in ("@reboot", "0 * * * *")]
    resolved_config_path = resolve_settings_path(config_path)
    config_args = f" --config {shlex.quote(str(resolved_config_path))}" if config_path else ""

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
    return [line.replace("%", r"\%") for line in [
        f"@reboot cd {app_dir} && {reboot_log_command}",
        f"*/{cron_interval} * * * * cd {app_dir} && {log_command}",
    ]]


def main() -> int:
    args = parse_args()
    if args.check_status or args.check_status_all:
        from status_check import check_status
        try:
            return check_status(args.config, args.status_output_dir, args.max_age_minutes, args.server_list, all_nodes=args.check_status_all)
        except (OSError, ValueError) as exc:
            print(f'상태 점검 실패: {exc}', file=sys.stderr)
            return 2
    try:
        if args.gateway_watchdog and platform.system() != "Linux":
            raise RuntimeError("게이트웨이 자동 재부팅은 Linux에서 지원합니다.")
        if args.install_crontab and os.name != "posix":
            raise RuntimeError("crontab 등록은 Linux/macOS에서 지원합니다.")
        if args.install_crontab and args.gateway_watchdog and not args.gateway_dry_run and os.geteuid() != 0:
            raise RuntimeError("자동 재부팅 감시는 sudo로 root crontab에 등록하세요.")
        if args.print_crontab or args.install_crontab:
            lines = build_crontab_lines(args.config, args.interval_minutes, args.gateway_watchdog, args.gateway_dry_run)
            if args.install_crontab:
                from cron_manager import install_crontab
                backup = install_crontab(lines, Path(__file__).resolve().parent, args.gateway_watchdog)
                print(f"crontab 등록 완료 (동일 작업 교체). 이전 설정 백업: {backup}")
            print("\n".join(lines))
            return 0
        if args.gateway_watchdog:
            from gateway_watchdog import run_watchdog
            return run_watchdog(Path(__file__).resolve().parent, args.gateway_dry_run)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"PulseDAV 실행 실패: {exc}", file=sys.stderr)
        return 1
    settings = load_settings(args.config)

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
        print_upload_targets(result)
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
    print_upload_targets(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
