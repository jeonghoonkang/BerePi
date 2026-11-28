"""Bounded automatic progress logs with an independent heartbeat."""
import json
import hashlib
import os
import sys
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

from db_locks import exclusive_file_lock

FORMAT = 'photo-browser-db-prune-progress-v1'
KST = timezone(timedelta(hours=9), 'KST')


class PruneProgress:
    def __init__(self, db, plan, operation, interval=5, log_path=None, files=5, max_bytes=1024 * 1024, terminal=None):
        self.db = Path(db).expanduser().resolve()
        self.plan = Path(plan).expanduser().resolve()
        name = 'photo-db-prune-' + hashlib.sha256(str(self.db).encode()).hexdigest()[:12] + '.progress.log'
        self.path = Path(log_path).expanduser().absolute() if log_path else self.plan.parent / name
        if files not in {1, 5} or interval <= 0 or max_bytes < 4096:
            raise ValueError('진행 로그는 1개 또는 5개, 출력 간격은 양수여야 합니다.')
        if self.path.is_symlink():
            raise ValueError('진행 로그 경로는 심볼릭 링크일 수 없습니다.')
        self.path = self.path.resolve()
        roots = [self.db]
        config_path = self.db / 'config.json'
        if config_path.is_file():
            config = json.loads(config_path.read_text(encoding='utf-8'))
            if config.get('managed_root'):
                roots.append(Path(config['managed_root']).expanduser().resolve())
            roots.extend(Path(s['root']).expanduser().resolve() for s in config.get('sources', []) if s.get('protocol', 'file') == 'file')
        family = {self.path, Path(str(self.path) + '.lock'), Path(str(self.path) + '.tmp'), *(Path(f'{self.path}.{i}') for i in range(1, 5))}
        reserved = {self.plan, *(Path(str(self.plan) + suffix) for suffix in ('-journal', '-wal', '-shm'))}
        if family & reserved or any(path == root or path.is_relative_to(root) for path in family for root in roots):
            raise ValueError('진행 로그는 DB·원본·관리 디렉토리 밖에, SQLite 계획과 다른 파일로 지정하세요.')
        self.files, self.max_bytes, self.interval = files, max_bytes, interval
        self.terminal = terminal
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.failure = None
        self.started = time.monotonic()
        self.state = {'format': FORMAT, 'operation': operation, 'status': 'running',
                      'started_at': datetime.now(KST).isoformat(), 'phase': 'starting',
                      'path': str(self.db), 'phase_count': 0, 'processed': 0, 'total': None,
                      'scope': 'current_invocation', 'db': str(self.db), 'plan': str(self.plan), 'log_file': str(self.path)}
        self.samples = deque(maxlen=100)

    def _check_owned(self, path):
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError(f'진행 로그가 일반 파일이 아닙니다: {path}')
        if path.exists() and path.stat().st_size:
            with path.open('rb') as stream:
                try:
                    first = json.loads(stream.readline(65536))
                except (ValueError, UnicodeError):
                    raise ValueError(f'다른 파일을 진행 로그로 덮어쓸 수 없습니다: {path}')
            if not isinstance(first, dict) or first.get('format') != FORMAT:
                raise ValueError(f'다른 파일을 진행 로그로 덮어쓸 수 없습니다: {path}')

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file_lock = exclusive_file_lock(Path(str(self.path) + '.lock'))
        try:
            self.file_lock.__enter__()
        except ValueError as exc:
            raise ValueError('같은 진행 로그를 다른 작업이 사용 중입니다. --progress-log 경로를 바꾸세요.') from exc
        try:
            for path in [self.path, Path(str(self.path) + '.tmp'), *(Path(f'{self.path}.{i}') for i in range(1, 5))]:
                self._check_owned(path)
            if self.files == 1:
                for i in range(1, 5):
                    Path(f'{self.path}.{i}').unlink(missing_ok=True)
            self.write()
            print(f'DB prune 진행 로그: {self.path} · 최대 {self.files}개 파일', file=sys.stderr, flush=True)
            self.thread = threading.Thread(target=self._heartbeat, name='db-prune-progress', daemon=True)
            self.thread.start()
        except BaseException:
            self.file_lock.__exit__(*sys.exc_info())
            raise
        return self

    def __call__(self, phase, count, path):
        with self.lock:
            if self.failure:
                raise OSError(f'필수 진행 로그 저장 실패: {self.failure}')
            self.state.update(phase=phase, phase_count=count, path=str(path)[-4096:])
            if phase in {'plan-total', 'delete-total'}:
                self.state.update(total=count, processed=0)
                self.samples.clear()
                self.samples.append((0, time.monotonic()))
            elif phase in {'plan', 'delete', 'plan-check', 'delete-check'}:
                self.state['processed'] = count
                if phase in {'plan', 'delete'}:
                    self.samples.append((count, time.monotonic()))

    def snapshot(self):
        current = time.monotonic()
        with self.lock:
            result = dict(self.state)
            samples = list(self.samples)
        elapsed = max(0, current - self.started)
        result.update(current_time=datetime.now(KST).isoformat(), elapsed_seconds=round(elapsed, 2), elapsed_minutes=round(elapsed / 60, 2),
                      progress_percent=None, estimated_remaining_seconds=None, estimated_finish_at=None,
                      estimated_total_seconds=None, estimate_status='unknown_total')
        total, processed = result['total'], result['processed']
        if total is not None:
            result['progress_percent'] = round(min(100, processed * 100 / total), 2) if total else 100
            result['estimate_status'] = 'collecting_samples'
            if processed >= total:
                result.update(estimated_remaining_seconds=0, estimated_finish_at=result['current_time'],
                              estimated_total_seconds=round(elapsed, 2), estimate_status='phase_complete')
            elif len(samples) >= min(10, total) + 1 and samples[-1][0] > samples[0][0]:
                average = (samples[-1][1] - samples[0][1]) / (samples[-1][0] - samples[0][0])
                idle = max(0, current - samples[-1][1])
                if idle > max(30, average * 3):
                    result['estimate_status'] = 'long_running_step'
                else:
                    remaining = max(1, (total - processed) * average - idle)
                    result.update(estimated_remaining_seconds=round(remaining, 2),
                                  estimated_finish_at=(datetime.now(KST) + timedelta(seconds=remaining)).isoformat(),
                                  estimated_total_seconds=round(elapsed + remaining, 2), estimate_status='estimated_current_phase')
        if result['phase'] == 'summary' and result['status'] == 'running':
            result.update(estimated_remaining_seconds=None, estimated_finish_at=None,
                          estimated_total_seconds=None, estimate_status='finalizing')
        if result['status'] in {'failed', 'interrupted'} or (result['status'] != 'running' and (total is None or processed < total)):
            result.update(estimated_remaining_seconds=None, estimated_finish_at=None,
                          estimated_total_seconds=None, estimate_status='stopped')
        return result

    def write(self):
        result = self.snapshot()
        payload = (json.dumps(result, ensure_ascii=False) + '\n').encode('utf-8', errors='backslashreplace')
        if self.files == 1:
            temporary = Path(str(self.path) + '.tmp')
            try:
                with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'wb') as stream:
                    stream.write(payload); stream.flush()
                os.replace(temporary, self.path)
            finally:
                temporary.unlink(missing_ok=True)
        else:
            if self.path.exists() and self.path.stat().st_size + len(payload) > self.max_bytes:
                Path(f'{self.path}.4').unlink(missing_ok=True)
                for i in range(3, 0, -1):
                    old = Path(f'{self.path}.{i}')
                    if old.exists():
                        os.replace(old, Path(f'{self.path}.{i + 1}'))
                os.replace(self.path, Path(f'{self.path}.1'))
            with os.fdopen(os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600), 'ab') as stream:
                stream.write(payload); stream.flush()
        if self.terminal is not None and self.terminal.render(result):
            return
        pct = ('미확정' if result['progress_percent'] is None else f"{result['progress_percent']:.2f}%")
        eta = result['estimated_finish_at'] or f"계산 대기({result['estimate_status']})"
        print(f"[{result['current_time']}] {result['status']} · 시작 {result['started_at']} · {result['phase']}: {result['phase_count']:,}"
              f" · 처리 {result['processed']:,}/{result['total'] if result['total'] is not None else '?'} ({pct})"
              f" · 경과 {result['elapsed_minutes']:.2f}분 · 종료 예상 {eta} · {result['path']}", file=sys.stderr, flush=True)

    def _heartbeat(self):
        while not self.stop.wait(self.interval):
            try:
                self.write()
            except Exception as exc:
                with self.lock:
                    self.failure = str(exc)
                print(f'필수 진행 로그 저장 실패: {exc}', file=sys.stderr, flush=True)
                return

    def finish(self, status):
        with self.lock:
            self.state['status'] = status

    def __exit__(self, kind, value, traceback):
        self.stop.set()
        self.thread.join(timeout=10)
        try:
            if self.thread.is_alive():
                raise OSError('진행 로그 I/O가 지연되어 종료 확인에 실패했습니다.')
            if kind:
                with self.lock:
                    self.state.update(status='interrupted' if kind is KeyboardInterrupt else 'failed', error=str(value)[-4096:])
            with self.lock:
                if not kind and self.state['status'] == 'running':
                    self.state['status'] = 'completed'
                self.state['finished_at'] = datetime.now(KST).isoformat()
                failure = self.failure
            if failure:
                raise OSError(f'필수 진행 로그 저장 실패: {failure}')
            self.write()
        finally:
            self.file_lock.__exit__(kind, value, traceback)
