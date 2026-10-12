"""Summarize local PulseDAV reports and optionally send plain text to Telegram."""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import re
import subprocess
import sys

from time_utils import SEOUL

MIN_BYTES = 100_000_000_000


def size_bytes(value: str, gib: bool) -> float:
    if gib:
        return float(value) * 1024**3
    match = re.fullmatch(r'(\d+(?:\.\d+)?)([KMGTPE]?)(?:i?B)?', value, re.I)
    if not match:
        raise ValueError(value)
    return float(match[1]) * 1024 ** ('KMGTPE'.index(match[2].upper()) + 1 if match[2] else 0)


def parse_report(path: Path) -> dict | None:
    text = path.read_text(encoding='utf-8')
    host = re.search(r'^- 호스트명:\s*(.+)$', text, re.M)
    ip = re.search(r'^- 내부 IP:\s*(.+)$', text, re.M)
    if not host or not ip:
        return None  # Exclude ipTIME reports and unrelated Markdown.
    stamp = re.search(r'^- 생성 시각:\s*(.+)$', text, re.M)
    moment = None
    if stamp:
        try:
            moment = datetime.strptime(stamp[1].strip(), '%Y-%m-%d %H:%M:%S KST').replace(tzinfo=SEOUL)
        except ValueError:
            pass
    if moment is None:
        name = re.fullmatch(r'pulse_(\d{8}_\d{6})\.md', path.name)
        if name:
            moment = datetime.strptime(name[1], '%Y%m%d_%H%M%S').replace(tzinfo=SEOUL)
        else:
            moment = datetime.fromtimestamp(path.stat().st_mtime, SEOUL)
    section = re.search(r'^## HDD 공간\s*\n(.*?)(?=^## |\Z)', text, re.M | re.S)
    disks = []
    if section:
        block = re.search(r'```(?:text)?\s*\n(.*?)```', section[1], re.S)
        if block:
            lines = block[1].strip().splitlines()
            gib = bool(lines and 'Size(GiB)' in lines[0])
            for line in lines[1:]:
                fields = line.split()
                if len(fields) < 6:
                    continue
                try:
                    if size_bytes(fields[1], gib) < MIN_BYTES:
                        continue
                    # macOS df -h has inode columns between Capacity and Mounted on.
                    mount = ' '.join(fields[8:] if len(fields) >= 9 and fields[7].endswith('%') else fields[5:])
                    used = float(fields[4].rstrip('%'))
                    if not fields[4].endswith('%') or not 0 <= used <= 100:
                        continue
                    disks.append(f"💽 {fields[0]} ({mount}): 빈 공간 {100-used:g}%")
                except ValueError:
                    continue
    return {'host': host[1].strip(), 'ip': ip[1].strip(), 'at': moment, 'disks': disks, 'path': path}


def collect(root: Path) -> tuple[list[dict], list[str]]:
    if not root.is_dir():
        raise ValueError(f'tinyGW 디렉터리가 없습니다: {root}')
    latest = {}
    errors = []
    for path in sorted(root.rglob('*.md')):
        try:
            report = parse_report(path)
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f'{path}: {type(exc).__name__}')
            continue
        if report and (report['host'] not in latest or report['at'] > latest[report['host']]['at']):
            latest[report['host']] = report
    return [latest[host] for host in sorted(latest)], errors


def render(reports: list[dict], errors: list[str]) -> str:
    lines = ['🖥️ tinyGW 전체 용량 현황', f'집계 시각: {datetime.now(SEOUL):%Y-%m-%d %H:%M:%S} KST',
             f'호스트 수: {len(reports)}', '']
    for report in reports:
        lines.extend([f"🖥️ Host: {report['host']}", f"🏠 Local IP: {report['ip']}",
                      f"최근 전송 시각: {report['at']:%Y-%m-%d %H:%M:%S} KST",
                      *(report['disks'] or ['💽 100GB 이상 파티션 정보 없음']), ''])
    if errors:
        lines.append(f'⚠️ 읽기/해석 실패 파일: {len(errors)}개 (서버 콘솔 참조)')
    return '\n'.join(lines).rstrip()


def send_text(message: str, executable: str, config: str | None, timeout: int) -> None:
    command = [str(Path(executable).expanduser())]
    if config:
        command += ['--config', str(Path(config).expanduser().resolve())]
    # Keep each message safely below Telegram's limit, including UTF-16 emoji units.
    remaining = message
    while remaining:
        chunk = remaining[:1800]
        if len(remaining) > 1800 and '\n' in chunk:
            chunk = chunk[:chunk.rfind('\n') + 1]
        remaining = remaining[len(chunk):]
        result = subprocess.run(command + ['--', chunk], capture_output=True, text=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError(f'telegram-send 종료 코드 {result.returncode}')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('tinyGW'), help='Local tinyGW directory (default: ./tinyGW)')
    parser.add_argument('--send', action='store_true', help='Send summary as Telegram text')
    parser.add_argument('--telegram-config', help='telegram-send configuration file')
    parser.add_argument('--executable', default='telegram-send')
    parser.add_argument('--timeout', type=int, default=60)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    try:
        reports, errors = collect(args.root.expanduser().resolve())
        for error in errors:
            print(error, file=sys.stderr)
        message = render(reports, errors)
        print(message)
        if not reports:
            print('집계 가능한 PulseDAV 보고서가 없습니다.', file=sys.stderr)
            return 1
        if args.send:
            send_text(message, args.executable, args.telegram_config, args.timeout)
            print('Telegram 전송 완료')
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f'tinyGW 집계/전송 실패: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
