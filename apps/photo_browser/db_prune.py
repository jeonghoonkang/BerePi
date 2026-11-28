"""Offline two-phase pruning of proven redundant media JSON, never media bytes."""
from collections import Counter
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import shlex
import sys
import time
import tempfile

from prune_memory import AdaptiveMemory

from db_audit import DBAudit, link
from db_locks import exclusive_file_lock
from library import EXTENSIONS, uid


FORMAT = 'photo-browser-verified-json-prune-v1'
STRING_MARKER = re.compile(rb'["\\]')
REASONS = {'verified': '현재 DB 정보 및 실제 소스·managed SHA-256 일치',
           'protected_reference': '현재 인덱스 또는 작업·복구 기록에서 참조',
           'historical_metadata_not_covered': '과거에만 있거나 현재와 다른 메타데이터·경로·상태가 있음',
           'missing_current_item': '현재 DB에 같은 media_id가 없음', 'invalid_hash': '과거 항목의 SHA-256 형식 오류',
           'invalid_or_empty_chunk': '미디어 JSON 형식 오류 또는 빈 청크',
           'source_not_verified': '실제 로컬 원본의 존재·SHA-256을 확인할 수 없음 (원격 포함)',
           'managed_not_verified': '현재 managed의 존재·SHA-256을 확인할 수 없음',
           'unreadable_or_invalid_json': 'JSON 읽기·형식·읽기 한도 문제', 'json_changed_after_plan': '계획 후 과거 JSON 내용 변경'}


def signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def reference_key(value):
    return value.casefold() if os.name == 'nt' else value


def covers(old, current):
    """Every nonempty historical metadata value must still be represented."""
    if old is None or old == '' or old == [] or old == {}:
        return True
    if isinstance(old, dict):
        return isinstance(current, dict) and all(key in current and covers(value, current[key]) for key, value in old.items())
    if isinstance(old, list):
        return isinstance(current, list) and all(any(covers(value, other) for other in current) for value in old)
    return type(old) == type(current) and old == current


def meaningful(item):
    result = {key: value for key, value in item.items() if key not in {'revision', 'last_seen_at', 'verification', 'locations'}}
    result['locations'] = [{key: value for key, value in loc.items() if key not in {'status', 'verified_at', 'merge_verification'}}
                           for loc in item.get('locations', [])]
    return result


def walk(root, skip_media=False, on_path=None):
    # Keep one directory iterator per depth, not a list of every pending folder.
    root = Path(root)
    stack = []
    try:
        if on_path: on_path(root)
        stack.append((root, os.scandir(root)))
        while stack:
            folder, entries = stack[-1]
            entry = next(entries, None)
            if entry is None:
                entries.close(); stack.pop(); continue
            if on_path: on_path(Path(entry.path))
            info = entry.stat(follow_symlinks=False)
            if link(info):
                if skip_media: raise ValueError(f'참조 검사 경로에 링크·정션이 있습니다: {entry.path}')
                continue
            if stat.S_ISDIR(info.st_mode):
                if not (skip_media and folder == root and entry.name == 'media'):
                    child = Path(entry.path)
                    if on_path: on_path(child)
                    stack.append((child, os.scandir(child)))
            elif stat.S_ISREG(info.st_mode):
                yield Path(entry.path)
    finally:
        for _, entries in stack: entries.close()


def strings(path, maximum, hasher=None, on_read=None):
    """Bounded streaming JSON string scanner, including escaped Unicode paths."""
    token = bytearray()
    inside = escaped = False
    with path.open('rb') as stream:
        while True:
            data = stream.read(1024 * 1024)
            if not data: break
            if on_read: on_read()
            if hasher is not None: hasher.update(data)
            position = 0
            if escaped:
                token.append(data[0]); position = 1; escaped = False
            while position < len(data):
                if not inside:
                    start = data.find(b'"', position)
                    if start < 0: break
                    token = bytearray(b'"'); inside = True; position = start + 1
                match = STRING_MARKER.search(data, position)
                end = match.end() if match else len(data)
                token.extend(data[position:end]); position = end
                if len(token) > maximum:
                    raise ValueError(f'참조 문자열 읽기 한도 초과: {path}')
                if not match: break
                if match.group() == b'"':
                    yield json.loads(token)
                    token.clear(); inside = False
                elif position == len(data):
                    escaped = True
                else:
                    token.append(data[position]); position += 1
        if inside:
            raise ValueError(f'미완성 JSON 문자열이 있어 참조 확인을 중단합니다: {path}')


@contextmanager
def offline(db, acknowledged, stop_timeout=120):
    if not acknowledged:
        raise ValueError('서버 확인·정상 종료를 허용하려면 --server-stopped를 지정하세요.')
    from server_control import ensure_server_stopped
    ensure_server_stopped(db, stop_timeout)
    with exclusive_file_lock(db / '.server.lock'), exclusive_file_lock(db / '.write.lock'):
        from source_health import audit_lock
        with audit_lock(db):
            if (db / '.photo-browser-pair-pending.json').exists():
                raise ValueError('미완료 DB 경로 트랜잭션이 있습니다. 먼저 정상 실행하여 복구하세요.')
            for path in (db / 'jobs').glob('*.json'):
                with path.open('rb') as stream:
                    prefix = stream.read(65536)
                found = re.search(rb'"status"\s*:\s*"([^"\\]+)"', prefix)
                if not found:
                    raise ValueError(f'작업 상태를 확인할 수 없습니다: {path}')
                if found.group(1) in {b'queued', b'running', b'stopping'}:
                    raise ValueError(f'실행·대기 상태의 작업 기록이 있습니다: {path}. 먼저 중지·저장 또는 복구하세요.')
            yield


class DiskSet:
    def __init__(self, connection):
        self.connection, self.count = connection, 0
        connection.execute('CREATE TABLE protected(path TEXT PRIMARY KEY) WITHOUT ROWID')

    def add(self, path):
        self.count += self.connection.execute('INSERT OR IGNORE INTO protected VALUES (?)', (path,)).rowcount

    def __contains__(self, path):
        return self.connection.execute('SELECT 1 FROM protected WHERE path=?', (path,)).fetchone() is not None

    def __len__(self): return self.count


class DiskItems:
    def __init__(self, connection, memory):
        self.connection, self.memory, self.count = connection, memory, 0
        connection.execute('CREATE TABLE items(id TEXT PRIMARY KEY, value TEXT NOT NULL) WITHOUT ROWID')

    def __contains__(self, mid):
        return self.connection.execute('SELECT 1 FROM items WHERE id=?', (mid,)).fetchone() is not None

    def __setitem__(self, mid, item):
        self.connection.execute('INSERT INTO items VALUES (?,?)', (mid, json.dumps(item, ensure_ascii=True)))
        self.count += 1

    def get(self, mid):
        if mid is None: return None
        key = ('item', mid)
        value = self.memory.get(key)
        if value is not None: return value
        row = self.connection.execute('SELECT value FROM items WHERE id=?', (mid,)).fetchone()
        if row is None: return None
        value = json.loads(row[0])
        self.memory.put(key, value)
        return value

    def __getitem__(self, mid):
        value = self.get(mid)
        if value is None: raise KeyError(mid)
        return value

    def __len__(self): return self.count


@contextmanager
def working_context(db, maximum, progress, memory_budget_mib):
    memory = AdaptiveMemory(memory_budget_mib)
    if hasattr(progress, 'set_memory_provider'): progress.set_memory_provider(memory.snapshot)
    # Scratch indexes are rebuilt under the offline lock on every invocation;
    # the durable plan remains independently resumable after a crash.
    with tempfile.TemporaryDirectory(prefix='photo-db-prune-') as temporary:
        connection = sqlite3.connect(str(Path(temporary) / 'lookup.sqlite'))
        try:
            tune_sqlite(connection)
            connection.execute('PRAGMA journal_mode=OFF')
            yield Context(db, maximum, progress, connection, memory)
        finally:
            connection.close()


def tune_sqlite(connection):
    connection.execute('PRAGMA cache_size=-512')
    connection.execute('PRAGMA mmap_size=0')
    connection.execute('PRAGMA temp_store=FILE')


class PruneAudit(DBAudit):
    def __init__(self, db, maximum, memory):
        self.memory = memory
        super().__init__(db, maximum)

    def read_bytes(self, relative, limit=None):
        path = self.safe_file(relative)
        before = signature(path.stat())
        size, maximum = before[2], limit or self.max_json_bytes
        if size > maximum: raise ValueError('JSON 읽기 한도를 초과했습니다.')
        self.memory.require_json(size)
        # BufferedReader.read(maximum) can allocate the entire maximum even
        # for a tiny file. Use the observed size, and reject concurrent growth.
        with path.open('rb') as stream:
            data = stream.read(size + 1)
        if len(data) != size or signature(path.stat()) != before:
            raise ValueError('JSON이 읽는 동안 변경되었습니다.')
        return data


class Context:
    def __init__(self, db, maximum, progress, connection, memory):
        self.connection, self.memory = connection, memory
        original_progress = progress
        def report(phase, count, path):
            memory.check()
            if original_progress: original_progress(phase, count, path)
        progress = report
        if progress: progress('initializing', 0, str(db))
        self.audit = PruneAudit(db, maximum, memory)
        if self.audit.manifest is None:
            raise ValueError('현재 index.json을 정상적으로 읽어야 정리할 수 있습니다.')
        self.db, self.maximum, self.progress = self.audit.db, maximum, progress
        if progress: progress('config', 0, 'config.json')
        self.config = json.loads(self.audit.read_bytes('config.json'))
        self.managed = Path(self.config['managed_root']).expanduser().resolve()
        if self.managed == self.db or self.managed.is_relative_to(self.db) or self.db.is_relative_to(self.managed):
            raise ValueError('DB와 managed 경로가 겹쳐 정리할 수 없습니다.')
        self.items = DiskItems(connection, memory)
        fingerprint = hashlib.sha256()
        self.protected = DiskSet(connection)
        connection.execute('CREATE TABLE current(path TEXT PRIMARY KEY) WITHOUT ROWID')
        connection.execute('CREATE TABLE refs(path TEXT PRIMARY KEY) WITHOUT ROWID')
        for path in self.audit.current:
            self.protected.add(reference_key(path))
            connection.execute('INSERT INTO current VALUES (?)', (path,))
        # Release index item-ID lists and path sets before reading photo chunks.
        self.audit.current.clear()
        self.audit.manifest = None
        for path in walk(self.db, skip_media=True,
                         on_path=lambda path: progress('discovering-references', 0, str(path))):
            if path.suffix.lower() in {'.json', '.jsonl'}:
                connection.execute('INSERT INTO refs VALUES (?)', (path.relative_to(self.db).as_posix(),))
        connection.commit()
        for (relative,) in connection.execute('SELECT path FROM refs ORDER BY path'):
            path = self.db / relative
            relative = path.relative_to(self.db).as_posix()
            if progress: progress('references', len(self.protected), relative)
            before = signature(path.stat())
            fingerprint.update(relative.encode()); fingerprint.update(b'\0' + str(before[2]).encode() + b'\0')
            for value in strings(path, maximum, fingerprint, lambda: progress('references-read', len(self.protected), relative)):
                value = value.replace('\\', '/')
                position = value.lower().find('media/')
                if value.lower().endswith('.json') and position >= 0 and (position == 0 or value[position - 1] == '/'):
                    self.protected.add(reference_key(self.audit.reference(value[position:])))
                # Preserve explicit references anywhere in operation/recovery JSON.
                for match in re.finditer(r'(?:^|/)(media/[^\s"<>]*?\.json)(?=$|[\s"<>])', value, re.I):
                    try: self.protected.add(reference_key(self.audit.reference(match.group(1))))
                    except ValueError: raise ValueError(f'안전하게 해석할 수 없는 미디어 참조: {relative}')
            if signature(path.stat()) != before:
                raise ValueError('참조 기록이 검사 중 변경되었습니다. 서버·작업을 종료하세요.')
            if progress: progress('references', len(self.protected), relative)
        for (relative,) in connection.execute('SELECT path FROM current ORDER BY path'):
            if progress: progress('current', len(self.items), relative)
            data = self.audit.read_bytes(relative)
            fingerprint.update(relative.encode()); fingerprint.update(hashlib.sha256(data).digest())
            page = json.loads(data)
            if not isinstance(page.get('items'), list):
                raise ValueError(f'현재 청크 items 형식 오류: {relative}')
            for item in page['items']:
                mid = item['media_id']
                if mid in self.items:
                    raise ValueError('현재 DB에 중복 media_id가 있어 정리를 중단합니다.')
                self.items[mid] = item
                if len(self.items) % 1000 == 0: progress('current', len(self.items), relative)
            del page, data
            item = None
            if progress: progress('current', len(self.items), relative)
        self.fingerprint = fingerprint.hexdigest()
        connection.commit()

    def physical(self, location, item, role):
        if location.get('protocol') != 'file' or not location.get('path'):
            return False
        path = Path(location['path']).expanduser().absolute()
        if self.progress: self.progress('hash-stat', self.memory.snapshot()['cache_entries'], str(path))
        if path.suffix.lower() not in EXTENSIONS:
            return False
        # No symlinks/junctions, including ancestor directories.
        for parent in [path, *path.parents]:
            info = parent.lstat()
            if link(info): return False
        resolved = path.resolve()
        if resolved.is_relative_to(self.db): return False
        if role == 'managed' and (not resolved.is_relative_to(self.managed) or resolved.is_relative_to(self.managed / '.trash')):
            return False
        before = path.stat()
        if not stat.S_ISREG(before.st_mode) or before.st_size != item['size_bytes']:
            return False
        key = (str(resolved), signature(before), item['sha256'])
        cached = self.memory.get(('physical', key))
        if cached is not None:
            return cached
        if self.progress: self.progress('hash', self.memory.snapshot()['cache_entries'], str(path))
        digest = hashlib.sha256()
        read_bytes = 0
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
                read_bytes += len(block)
                if self.progress: self.progress('hash-bytes', read_bytes, str(path))
        valid = signature(path.stat()) == signature(before) and digest.hexdigest() == item['sha256'].lower()
        self.memory.put(('physical', key), valid)
        return valid

    def covered(self, data):
        sha = hashlib.sha256(data).hexdigest()
        # Cache parsed coverage, but re-stat/reverify physical references on every use.
        cached = self.memory.get(('chunk', sha))
        if cached is not None:
            reason, ids = cached
        else:
            page = json.loads(data)
            if not isinstance(page, dict) or not isinstance(page.get('items'), list) or not page['items']:
                return 'invalid_or_empty_chunk'
            reason, ids = '', []
            for old in page['items']:
                if not isinstance(old, dict):
                    return 'invalid_or_empty_chunk'
                current = self.items.get(old.get('media_id'))
                if not current:
                    reason = 'missing_current_item'; break
                if not re.fullmatch('[0-9a-fA-F]{64}', str(old.get('sha256', ''))):
                    reason = 'invalid_hash'; break
                if not covers(meaningful(old), meaningful(current)):
                    reason = 'historical_metadata_not_covered'; break
                ids.append(current['media_id'])
        self.memory.put(('chunk', sha), (reason, ids))
        if reason: return reason
        for mid in ids:
            item = self.items[mid]
            for role in ('source', 'managed'):
                found = False
                for location in item['locations']:
                    if location['role'] != role or (role == 'managed' and location.get('status') != 'available'):
                        continue
                    try:
                        if self.physical(location, item, role):
                            found = True; break
                    except OSError:
                        continue
                if not found: return role + '_not_verified'
        return 'verified'


def connect_plan(path, create=False):
    path = Path(path).expanduser().absolute()
    if path.is_symlink() or (path.exists() and link(path.lstat())):
        raise ValueError('계획 파일은 링크·정션일 수 없습니다.')
    if create:
        # Exclusive creation protects unrelated files from accidental overwrite.
        with path.open('xb'): pass
    elif not path.is_file():
        raise ValueError('계획 파일이 없습니다.')
    connection = sqlite3.connect(str(path))
    connection.execute('PRAGMA trusted_schema=OFF')
    connection.execute('PRAGMA synchronous=FULL')
    tune_sqlite(connection)
    if create:
        connection.executescript('CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);'
                                'CREATE TABLE files(path TEXT PRIMARY KEY,sha TEXT,size INTEGER,verdict TEXT,reason TEXT,state TEXT);')
    return connection


def set_meta(connection, key, value):
    connection.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', (key, json.dumps(value)))


def metadata(connection):
    result = {key: json.loads(value) for key, value in connection.execute('SELECT key,value FROM meta')}
    if result.get('format') != FORMAT:
        raise ValueError('지원하는 JSON 정리 계획 파일이 아닙니다.')
    return result


def summary(connection, path):
    meta = metadata(connection)
    counts = {state: {'files': count, 'bytes': size or 0} for state, count, size in connection.execute(
        'SELECT state,COUNT(*),SUM(size) FROM files GROUP BY state')}
    reasons = dict(connection.execute('SELECT reason,COUNT(*) FROM files GROUP BY reason'))
    command = [sys.executable, str(Path(__file__).with_name('cli.py')), '--db', meta['db'], 'db-prune-apply',
               '--plan', str(Path(path).resolve()), '--server-stopped', '--confirm', meta['plan_id']]
    return {**meta, 'plan': str(Path(path).resolve()), 'counts': counts, 'reasons': reasons,
            'reason_labels': {reason: REASONS.get(reason, reason) for reason in reasons},
            'next_steps': ['현재 DB·소스·managed 파일이 변경되지 않도록 서버 종료 상태를 유지하세요.',
                           'counts.pending와 samples를 확인하세요. 삭제할 파일 수와 논리 용량입니다.',
                           'apply_command_posix 또는 apply_command_powershell로 검증 후 영구 삭제합니다.',
                           '중단 후 같은 실행 명령을 반복하면 미처리 후보부터 이어서 확인합니다.'],
            'apply_command_posix': shlex.join(command),
            'apply_command_powershell': '& ' + ' '.join("'" + value.replace("'", "''") + "'" for value in command),
            'samples': [{'path': row[0], 'size_bytes': row[1], 'state': row[2]} for row in connection.execute(
                "SELECT path,size,state FROM files WHERE verdict='eligible' LIMIT 20")],
            'kept_samples': [{'path': row[0], 'reason': row[1]} for row in connection.execute(
                "SELECT path,reason FROM files WHERE state IN ('kept','kept_after_change') LIMIT 20")],
            'warning': '삭제 대상은 과거 미디어 JSON뿐입니다. 삭제 후 되돌리기는 지원하지 않습니다. 실제 소스·managed 파일과 현재 DB·복구 기록은 삭제하지 않습니다.'}


def validate_plan_path(db, plan):
    plan = Path(plan).expanduser().resolve()
    db = Path(db).expanduser().resolve()
    if plan == db or plan.is_relative_to(db):
        raise ValueError('SQLite 계획 파일은 DB 디렉토리 밖에 저장하세요.')
    return plan


def count_prune_json(db, under='media', plan=None, resume=False, max_files=None, progress=None):
    """Count observed JSON paths only; no parsing, hashing, locks or DB writes."""
    db = Path(db).expanduser().resolve()
    if not db.is_dir(): raise ValueError('DB 디렉토리가 없습니다.')
    under = DBAudit.reference(under)
    if under != 'media' and not under.startswith('media/'):
        raise ValueError('--under는 media 또는 그 하위 디렉토리여야 합니다.')
    folder = db
    for part in under.split('/'):
        folder = folder / part
        if link(folder.lstat()) or not folder.is_dir():
            raise ValueError('안전한 media 하위 디렉토리가 아닙니다.')
    connection = None
    try:
        if resume:
            if not plan: raise ValueError('--resume 개수 조회에는 --plan이 필요합니다.')
            path = validate_plan_path(db, plan)
            if not path.is_file() or link(path.lstat()): raise ValueError('계획 파일이 없거나 안전하지 않습니다.')
            connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
            connection.execute('PRAGMA trusted_schema=OFF')
            tune_sqlite(connection)
            meta = metadata(connection)
            if meta['db'] != str(db) or meta['under'] != under:
                raise ValueError('계획의 DB·대상 범위가 다릅니다. 동일한 --db와 --under를 지정하세요.')
            if meta['status'] not in {'planning', 'partial', 'ready'}:
                raise ValueError('삭제를 시작한 계획은 검사 이어하기 개수를 조회할 수 없습니다. db-prune-status를 사용하세요.')
        total = planned = 0
        for path in walk(folder, on_path=(lambda path: progress('count', total, str(path))) if progress else None):
            if path.suffix.lower() != '.json': continue
            total += 1
            if connection and connection.execute('SELECT 1 FROM files WHERE path=?', (path.relative_to(db).as_posix(),)).fetchone():
                planned += 1
            if progress: progress('count', total, str(path))
        remaining = total - planned
        if progress:
            progress('count-total', total, str(folder))
            progress('count', total, str(folder))
        return {'status': 'counted', 'db': str(db), 'under': under,
                'total_json_files': total, 'already_planned_json_files': planned,
                'remaining_json_files': remaining,
                'invocation_json_files': min(remaining, max_files) if max_files else remaining,
                'resume': resume, 'read_only': True,
                'note': '현재·보호 청크를 포함한 검사 범위의 JSON 파일 수입니다. 삭제 가능한 파일 수가 아닙니다. 실행 중 파일이 변경되면 실제 검사 개수와 달라질 수 있습니다.'}
    finally:
        if connection: connection.close()


def plan_prune(db, plan, stopped=False, resume=False, maximum=64 * 1024 * 1024, max_files=None, under='media', progress=None, stop_timeout=120, memory_budget_mib=None):
    db = Path(db).expanduser().resolve()
    if not db.is_dir(): raise ValueError('DB 디렉토리가 없습니다.')
    plan = validate_plan_path(db, plan)
    under = DBAudit.reference(under)
    if under != 'media' and not under.startswith('media/'):
        raise ValueError('--under는 media 또는 그 하위 디렉토리여야 합니다.')
    if progress: progress('waiting-server', 0, str(db))
    with offline(db, stopped, stop_timeout), working_context(db, maximum, progress, memory_budget_mib) as context:
        progress = context.progress
        for source in context.config.get('sources', []):
            if source.get('protocol', 'file') == 'file' and plan.is_relative_to(Path(source['root']).expanduser().resolve()):
                raise ValueError('계획 파일은 원본 폴더 밖에 저장하세요.')
        if plan.is_relative_to(context.managed): raise ValueError('계획 파일은 managed 밖에 저장하세요.')
        folder = db / under
        if progress: progress('validating-scope', 0, str(folder))
        if not folder.is_dir() or folder.is_symlink() or not folder.resolve().is_relative_to(db / 'media'):
            raise ValueError('안전한 media 하위 디렉토리가 아닙니다.')
        connection = connect_plan(plan, create=not resume)
        try:
            if resume:
                meta = metadata(connection)
                if meta['db'] != str(db) or meta['fingerprint'] != context.fingerprint or meta['under'] != under:
                    raise ValueError('DB·참조 기록 또는 대상 경로가 변경되었습니다. 새 계획을 만드세요.')
                if meta['status'] not in {'planning', 'partial', 'ready'}:
                    raise ValueError('삭제를 시작한 계획은 미리보기 이어하기를 할 수 없습니다.')
            else:
                for key, value in {'format': FORMAT, 'plan_id': uid(), 'db': str(db), 'under': under,
                                   'fingerprint': context.fingerprint, 'maximum': maximum, 'status': 'planning'}.items():
                    set_meta(connection, key, value)
                connection.commit()
            count, partial = 0, False
            try:
                total = 0
                for path in walk(folder, on_path=(lambda path: progress('counting', total, str(path))) if progress else None):
                    if path.suffix.lower() != '.json': continue
                    relative = path.relative_to(db).as_posix()
                    if resume and connection.execute('SELECT 1 FROM files WHERE path=?', (relative,)).fetchone(): continue
                    total += 1
                    if max_files and total >= max_files: break
                if progress: progress('plan-total', total, str(folder))
                for path in walk(folder, on_path=(lambda path: progress('plan-walk', count, str(path))) if progress else None):
                    if path.suffix.lower() != '.json': continue
                    relative = path.relative_to(db).as_posix()
                    if connection.execute('SELECT 1 FROM files WHERE path=?', (relative,)).fetchone(): continue
                    if progress: progress('plan-check', count, relative)
                    size, sha, reason = path.stat().st_size, None, 'protected_reference'
                    if reference_key(relative) not in context.protected:
                        try:
                            data = context.audit.read_bytes(relative)
                            sha = hashlib.sha256(data).hexdigest()
                            reason = context.covered(data)
                        except (OSError, ValueError, KeyError, TypeError) as exc:
                            reason = 'unreadable_or_invalid_json'
                    eligible = reason == 'verified'
                    connection.execute('INSERT INTO files VALUES (?,?,?,?,?,?)',
                                       (relative, sha, size, 'eligible' if eligible else 'kept', reason, 'pending' if eligible else 'kept'))
                    count += 1
                    if count % 100 == 0: connection.commit()
                    if progress: progress('plan', count, relative)
                    if max_files and count >= max_files:
                        partial = True; break
            except KeyboardInterrupt:
                partial = True
            set_meta(connection, 'status', 'partial' if partial else 'ready')
            connection.commit()
            if progress: progress('summary', count, str(plan))
            return summary(connection, plan)
        finally:
            connection.close()


def apply_prune(db, plan, confirm, stopped=False, max_files=None, progress=None, stop_timeout=120, memory_budget_mib=None):
    db = Path(db).expanduser().resolve()
    plan = validate_plan_path(db, plan)
    if progress: progress('opening-plan', 0, str(plan))
    connection = connect_plan(plan)
    try:
        meta = metadata(connection)
        if meta['db'] != str(db) or confirm != meta['plan_id']:
            raise ValueError('DB 경로와 --confirm 계획 ID를 정확히 지정하세요.')
        if progress: progress('waiting-server', 0, str(db))
        with offline(db, stopped, stop_timeout), working_context(db, meta['maximum'], progress, memory_budget_mib) as context:
            progress = context.progress
            if context.fingerprint != meta['fingerprint']:
                raise ValueError('현재 DB 또는 복구 참조가 계획 이후 변경되었습니다. 삭제하지 않고 중단합니다.')
            set_meta(connection, 'status', 'applying'); connection.commit()
            count, partial = 0, False
            try:
                total = connection.execute("SELECT COUNT(*) FROM files WHERE verdict='eligible' AND state IN ('pending','deleting')").fetchone()[0]
                if progress: progress('delete-total', min(total, max_files) if max_files else total, str(plan))
                cursor = connection.execute("SELECT path,sha,state FROM files WHERE verdict='eligible' AND state IN ('pending','deleting')")
                while True:
                    batch = cursor.fetchmany(min(100, max_files - count) if max_files else 100)
                    if not batch: break
                    for relative, _, _ in batch:
                        if not relative.startswith('media/') or not relative.lower().endswith('.json') or reference_key(relative) in context.protected:
                            raise ValueError('계획에 보호 대상 또는 media 밖 경로가 있어 삭제하지 않습니다.')
                    # Durably reserve the batch before any unlink. A crash can be
                    # reconciled from presence + hash without one fsync per file.
                    connection.executemany("UPDATE files SET state='deleting' WHERE path=?", [(row[0],) for row in batch])
                    connection.commit()
                    for relative, expected, state in batch:
                        if progress: progress('delete-check', count, relative)
                        try:
                            path = context.audit.safe_file(relative)
                        except FileNotFoundError:
                            connection.execute('UPDATE files SET state=? WHERE path=?', ('recovered_deleted' if state == 'deleting' else 'already_missing', relative))
                        else:
                            before = signature(path.stat())
                            data = context.audit.read_bytes(relative)
                            reason = 'json_changed_after_plan' if hashlib.sha256(data).hexdigest() != expected else context.covered(data)
                            if reason != 'verified':
                                connection.execute("UPDATE files SET state='kept_after_change',reason=? WHERE path=?", (reason, relative))
                            else:
                                if signature(path.stat()) != before: raise ValueError('삭제 직전 과거 JSON이 변경되었습니다.')
                                path.unlink()
                                connection.execute("UPDATE files SET state='deleted' WHERE path=?", (relative,))
                        count += 1
                        if progress: progress('delete', count, relative)
                    connection.commit()
                    if max_files and count >= max_files:
                        partial = True; break
            except KeyboardInterrupt:
                partial = True
            set_meta(connection, 'status', 'partial_apply' if partial else 'completed'); connection.commit()
            if progress: progress('summary', count, str(plan))
            return summary(connection, plan)
    finally:
        connection.close()


def prune_status(plan):
    connection = connect_plan(plan)
    try: return summary(connection, plan)
    finally: connection.close()
