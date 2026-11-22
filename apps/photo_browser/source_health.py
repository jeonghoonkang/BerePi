"""Persist original-path incidents independently of the media catalog.

Checks never change photo records. Explicit, hash-verified repair is separate.
All journal/state writes cooperate with the library/backup write lock.
"""
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import threading
import time

from library import atomic_json, digest, read_json, uid


@contextmanager
def audit_lock(db, blocking=False):
    """Audit writers and backup share this lock; scans do not need to wait."""
    directory = Path(db) / 'source-path-health'
    directory.mkdir(parents=True, exist_ok=True)
    handle = (directory / '.write.lock').open('a+b')
    try:
        if os.name == 'nt':
            import msvcrt
            if handle.seek(0, 2) == 0: handle.write(b'0'); handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        yield
    finally:
        handle.close()


def stamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


class SourceHealth:
    def __init__(self, library, stream=None):
        self.library = library
        self.directory = library.db / 'source-path-health'
        self.stream = stream
        self.check_lock = threading.Lock()
        self.runtime_lock = threading.Lock()
        self.runtime = {'checking': False, 'processed': 0, 'total': 0, 'monitoring': False, 'interval': 5}
        self.inventory_key = None
        self.inventory = []
        self.hashes = {}
        self.seen = {}

    def catalog_signature(self):
        result = []
        for name in ('config.json', 'index.json'):
            try:
                value = (self.library.db / name).stat()
                result.append((value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns))
            except FileNotFoundError:
                result.append(None)
        return tuple(result)

    def references(self):
        signature = self.catalog_signature()
        config = self.library.config()
        sources = {s['source_id']: s for s in config['sources'] if s.get('protocol', 'file') == 'file'}
        if signature != self.inventory_key:
            references = []
            for item in self.library.items():
                if item['lifecycle']['status'] != 'active':
                    continue
                for location in item['locations']:
                    if location['role'] == 'source' and location.get('source_id') in sources and location.get('path'):
                        references.append({'media_id': item['media_id'], 'name': item['name'],
                            'source_id': location['source_id'], 'path': location['path'],
                            'sha256': item['sha256'], 'size_bytes': item['size_bytes'], 'mtime_ns': item.get('mtime_ns')})
            self.inventory, self.inventory_key = references, signature
            paths = {ref['path'] for ref in references}
            self.seen = {key: value for key, value in self.seen.items() if key in paths}
        return signature, sources, self.inventory

    @staticmethod
    def key(reference):
        value = [reference.get('media_id'), reference['source_id'], reference['path']]
        return hashlib.sha256(json.dumps(value, ensure_ascii=False).encode()).hexdigest()

    def source_root(self, source):
        root = self.library.local(source['root'])
        if not stat.S_ISDIR(root.stat().st_mode):
            raise ValueError('소스 루트가 디렉토리가 아닙니다.')
        return root

    def confined(self, source, value, root=None, managed=None):
        root = root if root is not None else self.source_root(source)
        raw = Path(value)
        path = self.library.local(value)
        if not raw.is_absolute() or not path.is_relative_to(root) or raw != path:
            raise ValueError('현재 소스 루트 밖이거나 링크를 거치는 원본 경로입니다. 소스 경로 설정을 확인하세요.')
        managed = managed if managed is not None else Path(self.library.config()['managed_root']).resolve()
        if path.is_relative_to(self.library.db) or path.is_relative_to(managed):
            raise ValueError('DB 또는 관리 복사본을 원본 경로로 사용할 수 없습니다.')
        return path

    def inspect(self, reference, source, cancel=lambda: False, root=None, managed=None):
        try:
            path = self.confined(source, reference['path'], root=root, managed=managed)
            info = path.stat()
            if not stat.S_ISREG(info.st_mode):
                return 'not_file', 'DB 원본 경로가 일반 파일이 아닙니다.'
            if info.st_size != reference['size_bytes']:
                return 'content_changed', 'DB에 기록된 원본 파일 크기와 다릅니다.'
            identity = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
            previous = self.seen.get(reference['path'])
            changed = (reference.get('mtime_ns') is not None and info.st_mtime_ns != reference['mtime_ns']) or (
                previous is not None and previous[:2] != identity[:2])
            if changed:
                def control():
                    if cancel(): raise InterruptedError('점검을 중지했습니다.')
                cached = self.hashes.get(reference['path'])
                if not cached or cached[0] != identity:
                    cached = (identity, digest(path, control=control))
                    if len(self.hashes) >= 10000: self.hashes.clear()
                    self.hashes[reference['path']] = cached
                if cached[1] != reference['sha256']:
                    return 'content_changed', '수정 시각 또는 파일이 바뀌었으며 SHA-256도 DB와 다릅니다.'
                after = path.stat()
                if identity != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                    return 'file_changing', '점검 중 파일이 변경되었습니다. 다음 점검에서 다시 확인합니다.'
            self.seen[reference['path']] = identity
            return None, None
        except FileNotFoundError:
            return 'missing', 'DB 원본 경로에서 파일을 찾을 수 없습니다. 이동·삭제·장치 연결 상태를 확인하세요.'
        except PermissionError as exc:
            return 'access_denied', '원본 접근 권한이 없습니다: ' + str(exc)
        except (OSError, ValueError) as exc:
            return 'unreachable', str(exc)

    def state(self):
        return read_json(self.directory / 'state.json', {'active': {}, 'resolved_count': 0, 'checked_at': None})

    def summary(self):
        summary = read_json(self.directory / 'summary.json', {'active_count': 0, 'resolved_count': 0, 'checked_at': None})
        with self.runtime_lock:
            return {**summary, **self.runtime}

    def page(self, view='open', offset=0):
        if view not in {'open', 'resolved'} or type(offset) is not int or offset < 0:
            raise ValueError('올바른 이력 종류와 페이지를 지정하세요.')
        if view == 'open':
            items = sorted(self.state()['active'].values(), key=lambda item: item['first_seen_at'], reverse=True)
            return {'items': items[offset:offset + 100], 'total': len(items), 'offset': offset}
        paths = sorted((self.directory / 'resolved').glob('*.json'), key=lambda path: path.stat().st_mtime_ns, reverse=True)
        return {'items': [read_json(path) for path in paths[offset:offset + 100]], 'total': len(paths), 'offset': offset}

    def event(self, record, action, at):
        event = {**record, 'event': action, 'at': at,
                 'elapsed_seconds': max(0, round(stamp(at) - stamp(record['first_seen_at'])))}
        local = datetime.fromisoformat(at).astimezone(timezone(timedelta(hours=9)))
        path = self.directory / 'events' / (local.strftime('%Y-%m-%d') + '.jsonl')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a+b') as stream:
            if stream.seek(0, 2):
                stream.seek(-1, 2)
                if stream.read(1) != b'\n': stream.write(b'\n')
            stream.write((json.dumps(event, ensure_ascii=False) + '\n').encode())
            stream.flush(); os.fsync(stream.fileno())
        if self.stream is not None:
            try:
                print('[{} KST] 원본 경로 {} · {} · {} · {} · 경과 {}초'.format(
                    local.strftime('%Y-%m-%d %H:%M:%S'), action, record['source_id'], record['path'],
                    record.get('resolution') if action in {'resolved', 'closed'} else record.get('problem'), event['elapsed_seconds']),
                    file=self.stream, flush=True)
            except (OSError, ValueError):
                pass

    def check(self, repeat_seconds=60, at=None, cancel=lambda: False):
        if not self.check_lock.acquire(blocking=False):
            return {'status': 'busy', **self.summary()}
        at = at or datetime.now(timezone.utc).isoformat()
        try:
            signature, sources, references = self.references()
            observed, checked, unavailable, roots = {}, set(), set(), {}
            managed = Path(self.library.config()['managed_root']).resolve()
            with self.runtime_lock:
                self.runtime.update(checking=True, processed=0, total=len(references), error=None)
            for source_id, source in sources.items():
                try:
                    roots[source_id] = self.source_root(source)
                except (OSError, ValueError) as exc:
                    reference = {'source_id': source_id, 'path': source['root'], 'kind': 'source_unavailable',
                                 'problem': '소스 루트에 접근할 수 없습니다: ' + str(exc)}
                    observed[self.key(reference)] = reference
                    unavailable.add(source_id)
            for index, reference in enumerate(references):
                if cancel(): return {'status': 'stopped'}
                key = self.key(reference)
                if reference['source_id'] not in unavailable:
                    kind, problem = self.inspect(reference, sources[reference['source_id']], cancel,
                                                 root=roots[reference['source_id']], managed=managed)
                    checked.add(key)
                    if kind: observed[key] = {**reference, 'kind': kind, 'problem': problem}
                with self.runtime_lock:
                    self.runtime['processed'] = index + 1
            if cancel(): return {'status': 'stopped'}
            # Backup pauses only audit persistence; ordinary scans may continue.
            try:
                with audit_lock(self.library.db):
                    if signature != self.catalog_signature():
                        return {'status': 'retry', 'message': 'DB가 변경되어 다음 주기에 다시 점검합니다.'}
                    state = self.state()
                    active = state['active']
                    # A disconnected root cannot prove earlier file errors fixed.
                    for key, old in active.items():
                        if old['source_id'] in unavailable and old.get('media_id'):
                            observed.setdefault(key, {**old, 'problem': '소스 루트 접근 불가로 원본 문제 재확인을 보류합니다.'})
                    for key, finding in observed.items():
                        old = active.get(key)
                        current = {**finding, 'issue_id': old['issue_id'] if old else uid(),
                                   'first_seen_at': old['first_seen_at'] if old else at,
                                   'last_seen_at': at, 'observations': old.get('observations', 0) + 1 if old else 1,
                                   'status': 'open', 'last_reported_at': old.get('last_reported_at') if old else None}
                        if not old or old['problem'] != finding['problem'] or stamp(at) - stamp(old['last_reported_at']) >= repeat_seconds:
                            current['last_reported_at'] = at
                            self.event(current, 'detected' if not old else 'unresolved', at)
                        active[key] = current
                    resolved = False
                    current_by_id = {(ref['media_id'], ref['source_id']): ref for ref in references}
                    for key in list(active):
                        if key in observed: continue
                        old = active.pop(key)
                        replacement = current_by_id.get((old.get('media_id'), old['source_id']))
                        if key in checked or (not old.get('media_id') and old['source_id'] in sources and old['source_id'] not in unavailable):
                            resolution, status = 'original_access_restored', 'resolved'
                            if not old.get('media_id') and sources[old['source_id']]['root'] != old['path']:
                                resolution = 'source_root_updated'
                        elif replacement and self.key(replacement) in checked and self.key(replacement) not in observed:
                            resolution, status = 'verified_db_path_updated', 'resolved'
                        else:
                            resolution, status = 'db_reference_removed_or_changed', 'closed'
                        record = {**old, 'status': status, 'resolved_at': at, 'resolution': resolution,
                                  'new_path': replacement['path'] if replacement else
                                      sources[old['source_id']]['root'] if not old.get('media_id') and old['source_id'] in sources else None}
                        atomic_json(self.directory / 'resolved' / (record['issue_id'] + '.json'), record)
                        self.event(record, status, at)
                        resolved = True
                    state.update(active=active, checked_at=at, checked_files=len(checked), tracked_files=len(references), source_count=len(sources))
                    if resolved:
                        state['resolved_count'] = len(list((self.directory / 'resolved').glob('*.json')))
                    atomic_json(self.directory / 'state.json', state)
                    summary = {key: value for key, value in state.items() if key != 'active'}
                    summary['active_count'] = len(active)
                    atomic_json(self.directory / 'summary.json', summary)
                    return {'status': 'completed', **summary}
            except BlockingIOError:
                return {'status': 'busy', 'message': '백업 또는 다른 점검이 기록 중입니다. 다음 주기에 재시도합니다.'}
        finally:
            with self.runtime_lock: self.runtime['checking'] = False
            self.check_lock.release()

    @contextmanager
    def running(self, interval=5, repeat_seconds=60):
        stop = threading.Event()
        with self.runtime_lock: self.runtime.update(monitoring=bool(interval), interval=interval)
        def worker():
            while not stop.is_set():
                try:
                    self.check(repeat_seconds, cancel=stop.is_set)
                except Exception as exc:
                    with self.runtime_lock: self.runtime['error'] = str(exc)
                    if self.stream is not None:
                        print('원본 경로 점검 실패: ' + str(exc), file=self.stream, flush=True)
                if stop.wait(interval): break
        thread = threading.Thread(target=worker, name='photo-source-health', daemon=True) if interval else None
        if thread: thread.start()
        try:
            yield
        finally:
            stop.set()
            if thread: thread.join(timeout=1)
            with self.runtime_lock: self.runtime['monitoring'] = False

    def origins(self, media_id):
        item = self.library.item(media_id)
        if item is None: raise ValueError('사진 항목이 없습니다.')
        sources = {source['source_id']: source for source in self.library.config()['sources']}
        result = []
        for location in item['locations']:
            if location['role'] != 'source': continue
            entry = {**location, 'folder': str(Path(location['path']).parent) if location.get('path') else None}
            if location.get('path') and location.get('source_id') in sources and location.get('protocol', 'file') == 'file':
                reference = {**location, 'size_bytes': item['size_bytes'], 'mtime_ns': item.get('mtime_ns'), 'sha256': item['sha256']}
                kind, problem = self.inspect(reference, sources[location['source_id']])
                entry.update(health=kind or 'ok', problem=problem)
            else: entry.update(health='not_checked', problem='로컬 원본 경로 점검 대상이 아닙니다.')
            result.append(entry)
        return {'media_id': media_id, 'items': result}

    def issue(self, issue_id):
        issue = next((entry for entry in self.state()['active'].values() if entry['issue_id'] == issue_id), None)
        if not issue: raise ValueError('현재 미해결 경로 문제가 아닙니다. 상태를 새로고침하세요.')
        return issue

    def find(self, issue_id, max_files=20000, seconds=5):
        issue = self.issue(issue_id)
        if not issue.get('media_id'): raise ValueError('소스 루트 경로를 먼저 설정·연결한 뒤 파일을 찾으세요.')
        source = next((s for s in self.library.config()['sources'] if s['source_id'] == issue['source_id']), None)
        if source is None: raise ValueError('소스 등록이 변경되었습니다. 다시 점검하세요.')
        root = self.source_root(source)
        managed = Path(self.library.config()['managed_root']).resolve()
        candidates, checked, limited = [], 0, False
        deadline = time.monotonic() + seconds
        def control():
            if time.monotonic() >= deadline: raise TimeoutError('검색 시간 한도')
        from scan_engine import local_media_files
        try:
            for _, info in local_media_files(self.library, {**source, 'recursive': True}, check=control):
                checked += 1
                if checked > max_files: limited = True; break
                path = self.confined(source, info['path'], root=root, managed=managed)
                if path.stat().st_size == issue['size_bytes'] and digest(path, control=control) == issue['sha256']:
                    candidates.append(str(path))
                    if len(candidates) >= 10: limited = True; break
        except TimeoutError:
            limited = True
        return {'candidates': candidates, 'checked_files': checked, 'limited': limited, 'root': str(root),
                'warning': '등록한 소스 루트 안에서만 검색합니다. 같은 내용의 복사본일 수도 있으므로 경로를 확인한 뒤 반영하세요.'}

    def repair(self, issue_id, new_path):
        issue = self.issue(issue_id)
        if not issue.get('media_id') or not isinstance(new_path, str): raise ValueError('사진 문제와 새 파일 경로가 필요합니다.')
        with self.library.writing():
            source = next((s for s in self.library.config()['sources'] if s['source_id'] == issue['source_id']), None)
            if source is None: raise ValueError('소스 등록이 변경되었습니다. 다시 점검하세요.')
            path = self.confined(source, str(self.library.local(new_path)))
            info = path.stat()
            if not path.is_file() or info.st_size != issue['size_bytes'] or digest(path) != issue['sha256']:
                raise ValueError('새 원본 파일의 크기·SHA-256이 DB와 다릅니다. 경로를 변경하지 않았습니다.')
            after = path.stat()
            if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns) != (
                    after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise ValueError('검증 중 새 원본 파일이 변경되었습니다. 다시 시도하세요.')
            items = self.library.items()
            item = next((item for item in items if item['media_id'] == issue['media_id']), None)
            if item is None: raise ValueError('사진 DB 항목이 변경되었습니다. 다시 점검하세요.')
            if item['sha256'] != issue['sha256'] or item['lifecycle']['status'] != 'active':
                raise ValueError('사진 정보가 변경되었습니다. 다시 점검하세요.')
            location = next((loc for loc in item['locations'] if loc['role'] == 'source'
                             and loc.get('source_id') == issue['source_id'] and loc.get('path') == issue['path']), None)
            if location is None: raise ValueError('DB 원본 경로가 이미 변경되었습니다. 다시 점검하세요.')
            location.update(path=str(path), uri=path.as_uri(), status='available')
            item['mtime_ns'] = info.st_mtime_ns
            item['revision'] += 1
            self.library.commit(items)
        self.check()
        return {'status': 'completed', 'media_id': issue['media_id'], 'old_path': issue['path'], 'new_path': str(path)}
