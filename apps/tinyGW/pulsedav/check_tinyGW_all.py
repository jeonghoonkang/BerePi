"""Summarize local PulseDAV reports and optionally send plain text to Telegram."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import re
import subprocess
import sys
import time

from time_utils import SEOUL
from pulsedav import (APP_DIR, REQUEST_ERRORS, build_session, build_webdav_config,
                      compose_webdav_url, load_settings)
from status_check import list_directory, safe_error

MIN_BYTES = 100_000_000_000


class WebDAVScanError(RuntimeError):
    def __init__(self, category: str):
        self.category = category
        super().__init__(category)


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


def collect(root: Path, progress=lambda message: None) -> tuple[list[dict], list[str]]:
    if not root.is_dir():
        raise ValueError(f'tinyGW 디렉터리가 없습니다: {root}')
    latest = {}
    errors = []
    progress('로컬 Markdown 파일 목록 조회 시작')
    paths = sorted(root.rglob('*.md'))
    for index, path in enumerate(paths, 1):
        progress(f'로컬 파일 읽기 {index}/{len(paths)}: {path.relative_to(root)}')
        try:
            report = parse_report(path)
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f'{path}: {type(exc).__name__}')
            continue
        if report and (report['host'] not in latest or report['at'] > latest[report['host']]['at']):
            latest[report['host']] = report
    return [latest[host] for host in sorted(latest)], errors


def collect_webdav(settings: dict, progress=lambda message: None) -> tuple[list[dict], list[str]]:
    config = build_webdav_config(settings)
    session = build_session(config)
    pending = ['tinyGW']
    visited = set()
    latest = {}
    errors = []
    read_count = 0
    try:
        while pending:
            directory = pending.pop()
            if directory in visited:
                continue
            visited.add(directory)
            progress(f'WebDAV 디렉터리 조회 시작: /{directory} (조회 {len(visited)}개, 대기 {len(pending)}개)')
            # A failed listing must not silently produce an incomplete inventory.
            try:
                entries = list_directory(session, config, directory)
                progress(f'디렉터리 조회 완료: 항목 {len(entries)}개')
            except REQUEST_ERRORS as exc:
                raise WebDAVScanError(safe_error(exc)) from exc
            # PulseDAV stores one host per directory and timestamps report names.
            # Read the newest valid system report; fall back if a newer file is unreadable.
            entries.sort(key=lambda entry: entry['path'], reverse=True)
            found_pulse = False
            for entry in entries:
                path = entry['path']
                if entry.get('error'):
                    errors.append(f"{path}: WebDAV metadata unavailable")
                    continue
                if entry['is_directory']:
                    pending.append(path)
                elif path.lower().endswith('.md'):
                    named_pulse = bool(re.fullmatch(r'pulse_\d{8}_\d{6}\.md', Path(path).name))
                    if not named_pulse or found_pulse:
                        continue
                    read_count += 1
                    progress(f'Markdown 읽기 시작 #{read_count}: /{path}')
                    try:
                        response = session.request('GET', compose_webdav_url(config, path), timeout=60)
                        response.raise_for_status()
                        modified = datetime.fromisoformat(entry['modified_at']) if entry.get('modified_at') else None
                        report = parse_report(Path(path), response.content.decode('utf-8-sig'), modified)
                    except REQUEST_ERRORS + (OSError, UnicodeError, ValueError):
                        errors.append(f'{path}: report read/parse failed')
                        progress(f'Markdown 읽기 실패 #{read_count} (누적 실패 {len(errors)}개)')
                        continue
                    if report and (report['host'] not in latest or report['at'] > latest[report['host']]['at']):
                        latest[report['host']] = report
                    if report and named_pulse:
                        found_pulse = True
                    progress(f'Markdown 처리 완료 #{read_count} (집계 호스트 {len(latest)}개)')
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


def send_text(message: str, executable: str, config: str | None, timeout: int,
              progress=lambda message: None) -> None:
    command = [str(Path(executable).expanduser())]
    if config:
        command += ['--config', str(Path(config).expanduser().resolve())]
    # Keep each message safely below Telegram's limit, including UTF-16 emoji units.
    remaining = message
    index = 0
    while remaining:
        index += 1
        chunk = remaining[:1800]
        if len(remaining) > 1800 and '\n' in chunk:
            chunk = chunk[:chunk.rfind('\n') + 1]
        remaining = remaining[len(chunk):]
        progress(f'Telegram 문자 전송 시작 #{index} (남은 문자 {len(remaining)}자)')
        result = subprocess.run(command + ['--', chunk], capture_output=True, text=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError(f'telegram-send 종료 코드 {result.returncode}')
        progress(f'Telegram 문자 전송 완료 #{index}')


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
    started = time.monotonic()

    def progress(message):
        elapsed = time.monotonic() - started
        print(f'[{datetime.now(SEOUL):%Y-%m-%d %H:%M:%S} KST | 경과 {elapsed:.1f}초] {message}',
              file=sys.stderr, flush=True)

    progress('tinyGW 집계 시작')
    config_path = Path(args.config).expanduser().resolve() if args.config else APP_DIR / 'settings.json'
    try:
        with config_path.open(encoding='utf-8') as source:
            raw_settings = json.load(source)
        if not isinstance(raw_settings, dict) or not isinstance(raw_settings.get('webdav'), dict):
            raise ValueError('webdav 설정 항목이 필요합니다')
    except (OSError, ValueError) as exc:
        progress('설정 파일 검증 실패 — 실행 중단')
        print(f'설정 파일을 읽을 수 없거나 형식이 잘못되었습니다: {config_path} ({type(exc).__name__})', file=sys.stderr)
        return 1
    print(f'사용 설정 파일: {config_path}')
    progress('설정 파일 검증 완료')
    settings = load_settings(config_path)
    telegram = settings.get('telegram', {})
    timeout = args.timeout if args.timeout is not None else int(telegram.get('timeout_seconds', 60))
    if timeout <= 0:
        parser.error('--timeout must be positive')
    try:
        reports, errors = (collect(args.root.expanduser().resolve(), progress) if args.root else collect_webdav(settings, progress))
        progress(f'집계 완료: 호스트 {len(reports)}개, 읽기/해석 실패 {len(errors)}개')
        for error in errors:
            print(error, file=sys.stderr)
        message = render(reports, errors)
        logs_directory = args.logs_dir.expanduser().resolve()
        progress(f'집계 로그 저장 시작: {logs_directory}')
        saved = save_summary(message, logs_directory)
        progress(f'output 파일 저장 완료: {saved}')
        print(saved.read_text(encoding='utf-8'), end='')
        print(f'집계 파일 저장: {saved}')
        if not reports:
            progress('집계 가능한 보고서 없음 — 실행 종료')
            print('집계 가능한 PulseDAV 보고서가 없습니다.', file=sys.stderr)
            return 1
        if args.send:
            telegram_config = args.telegram_config
            if telegram_config is None and telegram.get('config_path'):
                configured = Path(telegram['config_path']).expanduser()
                telegram_config = str(configured if configured.is_absolute() else APP_DIR / configured)
            send_text(saved.read_text(encoding='utf-8'), args.executable or telegram.get('executable') or 'telegram-send',
                      telegram_config, timeout, progress)
            print('Telegram 전송 완료')
        progress('전체 작업 완료')
        return 0
    except REQUEST_ERRORS + (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        progress('작업 실패 — 실행 중단')
        detail = exc.category if isinstance(exc, WebDAVScanError) else safe_error(exc)
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
