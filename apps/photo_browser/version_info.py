"""Release identity and bounded, stoppable terminal reminders."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import math
from pathlib import Path
import subprocess
import sys
import threading

VERSION = '2026.11.11.1'
RELEASE_DATE = '2026-11-11'
DEFAULT_LOG_INTERVAL = 1800


def version_info():
    info = {'version': VERSION, 'release_date': RELEASE_DATE,
            'revision': None, 'committed_at': None, 'modified': False}
    directory = Path(__file__).resolve().parent
    try:
        def git(*args):
            return subprocess.run(['git', *args], cwd=directory, check=True,
                                  capture_output=True, text=True, timeout=2).stdout.strip()
        lines = git('log', '-1', '--format=%h%n%cI', '--', '.').splitlines()
        if len(lines) == 2:
            info.update(revision=lines[0], committed_at=lines[1],
                        modified=bool(git('status', '--porcelain', '--untracked-files=no', '--', '.')))
    except (OSError, subprocess.SubprocessError):
        pass  # A copied distribution can run without Git or a .git directory.
    return info


def version_label(info):
    label = 'Photo Browser v{} · 버전 기준일 {}'.format(info['version'], info['release_date'])
    if info['revision']:
        label += ' · 커밋 {} ({})'.format(info['revision'], info['committed_at'])
    if info['modified']:
        label += ' · 미커밋 변경 포함'
    return label


def log_interval(value):
    import argparse
    try:
        seconds = float(value)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError('버전 출력 간격은 0 이상의 초 단위 숫자여야 합니다.')
    if not math.isfinite(seconds) or seconds < 0:
        raise argparse.ArgumentTypeError('버전 출력 간격은 0 이상의 초 단위 숫자여야 합니다.')
    return seconds


@contextmanager
def version_logging(info, interval=DEFAULT_LOG_INTERVAL, stream=None):
    """Use a startup snapshot: pulling code cannot relabel an already running server."""
    stream = stream if stream is not None else sys.stderr
    label = version_label(info)
    print(label, file=stream, flush=True)
    stopped = threading.Event()
    def report():
        while not stopped.wait(interval):
            timestamp = datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S KST')
            try:
                print('[{}] 실행 버전: {}'.format(timestamp, label), file=stream, flush=True)
            except (OSError, ValueError):
                break
    thread = threading.Thread(target=report, name='photo-browser-version', daemon=True) if interval else None
    if thread:
        thread.start()
    try:
        yield
    finally:
        stopped.set()
        if thread:
            thread.join(timeout=1)
