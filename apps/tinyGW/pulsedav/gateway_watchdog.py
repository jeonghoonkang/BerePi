"""Linux default-gateway checks; cron starts a fresh check each hour."""
from __future__ import annotations

import ipaddress
import json
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

from time_utils import SEOUL


def executable(name: str) -> str:
    result = shutil.which(name, path=os.environ.get("PATH", "") + ":/usr/sbin:/sbin:/usr/bin:/bin")
    if not result:
        raise RuntimeError(f"필수 명령을 찾을 수 없습니다: {name}")
    return result


def default_gateway(ip_command: str) -> str | None:
    result = subprocess.run([ip_command, "-j", "-4", "route", "show", "default"],
                            capture_output=True, text=True, timeout=10, check=True)
    routes = json.loads(result.stdout)
    for route in sorted(routes, key=lambda item: int(item.get("metric", 0))):
        if route.get("gateway"):
            return str(ipaddress.IPv4Address(route["gateway"]))
    return None


def ping_gateway(command: str, gateway: str) -> bool:
    result = subprocess.run([command, "-n", "-c", "1", "-W", "3", gateway],
                            capture_output=True, timeout=10)
    if result.returncode not in (0, 1):
        raise RuntimeError(f"ping 명령 실행 오류 (exit={result.returncode})")
    return result.returncode == 0


def log(message: str) -> None:
    print(f"[{datetime.now(SEOUL).isoformat(timespec='seconds')}] {message}", flush=True)


def monitor(*, probe, reboot, dry_run=False, clock=time.monotonic, sleep=time.sleep) -> int:
    """Require failed samples for a full 30 minutes; any success cancels reboot."""
    failed_since = None
    while True:
        started = clock()
        gateway, reachable = probe()
        if reachable:
            log(f"게이트웨이 {gateway}: 정상 (연속 실패 시간 초기화)")
            return 0
        if failed_since is None:
            failed_since = started
        elapsed = clock() - failed_since
        log(f"게이트웨이 {gateway or '없음'}: 접속 실패, {int(elapsed)}초 경과")
        if elapsed >= 30 * 60:
            if dry_run:
                log("DRY RUN: 30분 연속 실패, 재부팅 생략")
            else:
                log("30분 연속 실패: 시스템 재부팅 요청")
                reboot()
            return 1
        sleep(min(6 * 60, 30 * 60 - elapsed))


def run_watchdog(app_dir: Path, dry_run: bool = False) -> int:
    import fcntl
    if not dry_run and os.geteuid() != 0:
        raise RuntimeError("자동 재부팅은 root 권한이 필요합니다. sudo로 실행하거나 --gateway-dry-run을 사용하세요.")
    # Separate from reporting so a WebDAV failure never prevents gateway checks.
    with (app_dir / ".gateway-watchdog.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log("이미 게이트웨이 점검 중: 중복 실행 생략")
            return 0
        ip_command, ping_command = executable("ip"), executable("ping")
        reboot_command = executable("reboot") if not dry_run else None

        def probe():
            gateway = default_gateway(ip_command)
            return gateway, bool(gateway and ping_gateway(ping_command, gateway))

        def reboot():
            subprocess.run([reboot_command], check=True, timeout=30)

        return monitor(probe=probe, reboot=reboot, dry_run=dry_run)
