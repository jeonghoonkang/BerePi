"""Summarize local PulseDAV reports and optionally send plain text to Telegram."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import re
import subprocess
import sys

from time_utils import SEOUL
from pulsedav import (APP_DIR, REQUEST_ERRORS, build_session, build_webdav_config,
                      compose_webdav_url, load_settings)
from status_check import list_directory, safe_error

MIN_BYTES = 100_000_000_000


def size_bytes(value: str, gib: bool) -> float:
    if gib:
        return float(value) * 1024**3
    match = re.fullmatch(r'(\d+(?:\.\d+)?)([KMGTPE]?)(?:i?B)?', value, re.I)
    if not match:
        raise ValueError(value)
    return float(match[1]) * 1024 ** ('KMGTPE'.index(match[2].upper()) + 1 if match[2] else 0)


def parse_report(path: Path, text: str | None = None, modified: datetime | None = None) -> dict | None:
    if text is None:
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
            moment = modified or datetime.fromtimestamp(path.stat().st_mtime, SEOUL)
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


def collect_webdav(settings: dict) -> tuple[list[dict], list[str]]:
    config = build_webdav_config(settings)
    session = build_session(config)
    pending = ['tinyGW']
    visited = set()
    latest = {}
    errors = []
    try:
        while pending:
            directory = pending.pop()
            if directory in visited:
                continue
            visited.add(directory)
            # A failed listing must not silently produce an incomplete inventory.
            try:
                entries = list_directory(session, config, directory)
            except REQUEST_ERRORS as exc:
                raise RuntimeError(f'WebDAV PROPFIND /{directory}: {safe_error(exc)}') from exc
            for entry in entries:
                path = entry['path']
                if entry.get('error'):
                    errors.append(f"{path}: WebDAV metadata unavailable")
                    continue
                if entry['is_directory']:
                    pending.append(path)
                elif path.lower().endswith('.md'):
                    try:
                        response = session.request('GET', compose_webdav_url(config, path), timeout=60)
                        response.raise_for_status()
                        modified = datetime.fromisoformat(entry['modified_at']) if entry.get('modified_at') else None
                        report = parse_report(Path(path), response.content.decode('utf-8-sig'), modified)
                    except REQUEST_ERRORS + (OSError, UnicodeError, ValueError):
                        errors.append(f'{path}: report read/parse failed')
                        continue
                    if report and (report['host'] not in latest or report['at'] > latest[report['host']]['at']):
                        latest[report['host']] = report
    finally:
        if hasattr(session, 'close'):
            session.close()
    return [latest[host] for host in sorted(latest)], errors


def save_summary(message: str, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"tinyGW_all_{datetime.now(SEOUL):%Y%m%d_%H%M%S_%f}.txt"
    with path.open('x', encoding='utf-8') as output:
        output.write(message + '\n')
    return path


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
    parser.add_argument('--config', help='PulseDAV settings JSON for WebDAV and Telegram')
    parser.add_argument('--root', type=Path, help='Optional local directory instead of WebDAV /tinyGW')
    parser.add_argument('--logs-dir', type=Path, default=APP_DIR / 'logs', help='Saved summary directory')
    parser.add_argument('--send', action='store_true', help='Send summary as Telegram text')
    parser.add_argument('--telegram-config', help='telegram-send configuration file')
    parser.add_argument('--executable')
    parser.add_argument('--timeout', type=int)
    args = parser.parse_args()
    config_path = Path(args.config).expanduser().resolve() if args.config else APP_DIR / 'settings.json'
    try:
        with config_path.open(encoding='utf-8') as source:
            raw_settings = json.load(source)
        if not isinstance(raw_settings, dict) or not isinstance(raw_settings.get('webdav'), dict):
            raise ValueError('webdav 설정 항목이 필요합니다')
    except (OSError, ValueError) as exc:
        print(f'설정 파일을 읽을 수 없거나 형식이 잘못되었습니다: {config_path} ({type(exc).__name__})', file=sys.stderr)
        return 1
    print(f'사용 설정 파일: {config_path}')
    settings = load_settings(config_path)
    telegram = settings.get('telegram', {})
    timeout = args.timeout if args.timeout is not None else int(telegram.get('timeout_seconds', 60))
    if timeout <= 0:
        parser.error('--timeout must be positive')
    try:
        reports, errors = (collect(args.root.expanduser().resolve()) if args.root else collect_webdav(settings))
        for error in errors:
            print(error, file=sys.stderr)
        message = render(reports, errors)
        saved = save_summary(message, args.logs_dir.expanduser().resolve())
        print(saved.read_text(encoding='utf-8'), end='')
        print(f'집계 파일 저장: {saved}')
        if not reports:
            print('집계 가능한 PulseDAV 보고서가 없습니다.', file=sys.stderr)
            return 1
        if args.send:
            telegram_config = args.telegram_config
            if telegram_config is None and telegram.get('config_path'):
                configured = Path(telegram['config_path']).expanduser()
                telegram_config = str(configured if configured.is_absolute() else APP_DIR / configured)
            send_text(saved.read_text(encoding='utf-8'), args.executable or telegram.get('executable') or 'telegram-send',
                      telegram_config, timeout)
            print('Telegram 전송 완료')
        return 0
    except REQUEST_ERRORS + (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        detail = safe_error(exc)
        hints = {'HTTP 401': 'WebDAV ID·비밀번호 또는 앱 비밀번호를 확인하세요.',
                 'HTTP 403': '/tinyGW 디렉터리 목록·파일 읽기 권한을 확인하세요.',
                 'HTTP 404': 'webdav.hostname·root 및 그 아래 /tinyGW 존재 여부를 확인하세요.',
                 'HTTP 405': '접속 경로가 PROPFIND를 지원하는 WebDAV 주소인지 확인하세요.',
                 'tls_certificate_error': '서버 인증서와 신뢰 체인을 확인하세요.',
                 'dns_error': 'WebDAV 서버 호스트명과 DNS를 확인하세요.',
                 'timeout': '서버 응답 지연·방화벽·네트워크를 확인하세요.',
                 'connection_refused': '서버 주소·포트와 서비스 실행 상태를 확인하세요.'}
        print(f'tinyGW 집계/저장/전송 실패: {detail} — {hints.get(detail, "접속 설정·네트워크·저장 권한을 확인하세요.")}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
