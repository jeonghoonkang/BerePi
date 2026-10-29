"""Send local/public IP and Docker status without a WebDAV connection."""
from __future__ import annotations

import argparse
from datetime import datetime

from pulsedav import (
    get_docker_status, get_ip_route_default, get_public_ip, hostname,
    send_telegram_report,
)
from time_utils import SEOUL


def build_report() -> str:
    internal_ip, gateway = get_ip_route_default()
    return '\n'.join([
        'IP / Docker 운영 상태',
        f'시각: {datetime.now(SEOUL):%Y-%m-%d %H:%M:%S KST}',
        f'호스트: {hostname()}',
        f'내부 IP: {internal_ip}',
        f'공인 IP: {get_public_ip()}',
        f'게이트웨이: {gateway}',
        '', 'Docker 서버 / 실행 중인 컨테이너:',
        get_docker_status() or '실행 중인 컨테이너 없음',
    ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='Print without sending.')
    parser.add_argument('--telegram-config', default='', help='telegram-send config file path.')
    parser.add_argument('--executable', default='telegram-send', help='telegram-send executable path.')
    args = parser.parse_args(argv)
    report = build_report()
    if args.dry_run:
        print(report)
        return 0
    settings = {'telegram': {
        'enabled': True, 'executable': args.executable,
        'config_path': args.telegram_config, 'timeout_seconds': 60,
    }}
    # At most 3000 UTF-16 units per message, including non-BMP characters.
    for start in range(0, len(report), 1500):
        result = send_telegram_report(settings, report[start:start + 1500], None)
        if result['status'] != 'sent':
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
