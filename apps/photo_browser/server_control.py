"""Local, instance-addressed shutdown requests; never kill a PID from history."""
import json
import os
from pathlib import Path
import sys
import threading
import time

from db_locks import LockBusyError, exclusive_file_lock
from library import atomic_json, now, uid


RUNTIME = '.server-runtime'
REQUEST = '.server-stop-request'
HISTORY = 'server-history.txt'
HISTORY_LIMIT = 1000


def load_record(path):
    if path.is_symlink() or (path.exists() and getattr(path.lstat(), 'st_file_attributes', 0) & 0x400):
        raise ValueError(f'서버 제어 기록이 링크·정션입니다: {path}')
    if not path.exists():
        return None
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError(f'서버 제어 기록이 너무 큽니다: {path}')
    return json.loads(path.read_text(encoding='utf-8'))


def save_record(path, record):
    # Validate an existing control file before replacing it. Records contain no
    # environment variables/passwords and are readable only by the local owner.
    load_record(path)
    atomic_json(path, record)
    if os.name != 'nt':
        path.chmod(0o600)


def history(db):
    path = db / HISTORY
    if path.is_symlink() or (path.exists() and getattr(path.lstat(), 'st_file_attributes', 0) & 0x400):
        raise ValueError('서버 실행 히스토리가 링크·정션입니다.')
    if not path.exists():
        return []
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('서버 실행 히스토리가 너무 큽니다.')
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def record_history(db, record):
    rows = (history(db) + [record])[-HISTORY_LIMIT:]
    path = db / HISTORY
    temporary = db / (HISTORY + '.' + uid() + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        if os.name != 'nt':
            temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def lock_available(db):
    try:
        with exclusive_file_lock(db / '.server.lock'):
            return True
    except LockBusyError:
        return False


def ensure_server_stopped(db, timeout=120, stream=None):
    """Ask only the server owning this DB to drain; lock remains authoritative."""
    db = Path(db).resolve()
    stream = sys.stderr if stream is None else stream
    if lock_available(db):
        print('서버 확인: 실행 중인 내장 Photo Browser 서버가 없습니다.', file=stream, flush=True)
        return
    record = load_record(db / RUNTIME)
    if record is None:
        # A deleted runtime record can be recovered from local launch history.
        rows = history(db)
        record = rows[-1] if rows else None
    if (not isinstance(record, dict) or record.get('db') != str(db)
            or record.get('state') != 'running' or not isinstance(record.get('instance_id'), str)
            or not isinstance(record.get('pid'), int) or record['pid'] <= 0):
        raise ValueError('서버 잠금이 사용 중이지만 자동 종료 가능한 실행 기록이 없습니다. '
                         '이전 버전·외부 WSGI 서비스는 직접 종료하고, 새 버전으로 한 번 실행해야 합니다.')
    request = {'instance_id': record['instance_id'], 'request_id': uid(), 'db': str(db),
               'requested_at': now(), 'action': 'stop_for_maintenance'}
    save_record(db / REQUEST, request)
    print(f"서버 종료 요청: PID {record['pid']} · DB {db}. 작업 중지·저장 및 종료를 기다립니다.",
          file=stream, flush=True)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if lock_available(db):
            print('서버 종료 확인 완료. 정리 작업을 진행합니다.', file=stream, flush=True)
            return
        current = load_record(db / RUNTIME)
        if current and current.get('instance_id') != record['instance_id']:
            raise ValueError('종료 대기 중 서버가 새로 시작되었습니다. 서비스 자동 재시작을 중지한 뒤 실행하세요.')
        time.sleep(0.2)
    raise ValueError(f'{timeout:g}초 안에 서버 종료를 확인하지 못했습니다. 정리를 실행하지 않습니다. '
                     '작업 저장·서비스 상태를 확인하거나 --server-stop-timeout을 늘리세요.')


class LocalServerControl:
    def __init__(self, db, controller, app, host, port):
        self.db, self.controller, self.app = db, controller, app
        self.record = {'instance_id': controller.instance_id, 'pid': os.getpid(), 'db': str(db),
                       'started_at': now(), 'state': 'running', 'host': host, 'port': port,
                       'executable': sys.executable, 'cwd': os.getcwd()}
        self.done = threading.Event()
        self.thread = None

    def start(self):
        save_record(self.db / RUNTIME, self.record)
        record_history(self.db, self.record)
        self.thread = threading.Thread(target=self.watch, name='photo-local-control', daemon=True)
        self.thread.start()

    def watch(self):
        while not self.done.wait(0.2):
            try:
                request = load_record(self.db / REQUEST)
                if (not isinstance(request, dict) or request.get('db') != str(self.db)
                        or request.get('instance_id') != self.controller.instance_id
                        or request.get('action') != 'stop_for_maintenance'):
                    continue
                with self.controller.lock:
                    if self.controller.pending:
                        # Do not turn an already accepted web restart into a stop.
                        return
                    self.controller.stopping = True
                jobs = self.app.extensions['photo_jobs_maintenance']
                while jobs() and not self.done.wait(0.2):
                    pass
                if not self.done.is_set():
                    self.controller.shutdown()
                return
            except (OSError, ValueError, KeyError, TypeError) as exc:
                print(f'로컬 서버 종료 요청 처리 실패: {exc}', file=sys.stderr, flush=True)
                return

    def stop_watching(self):
        self.done.set()
        if self.thread:
            self.thread.join(timeout=5)

    def finish(self):
        self.stop_watching()
        final = {**self.record, 'state': 'stopped', 'stopped_at': now()}
        save_record(self.db / RUNTIME, final)
        record_history(self.db, final)
