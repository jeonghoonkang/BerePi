"""Resumable scan inventory and result journal; no original files are modified."""
import copy
import errno
import json
import os
import shutil
import socket
import tempfile
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit

from library import EXTENSIONS, VIDEO_EXTENSIONS, atomic_json, component, digest, metadata, now, read_json, uid

MIB = 1024 * 1024
RECORD_ESTIMATE = 16384


def local_media_files(library, source, check=None):
    """Share source traversal rules between scanning and startup inventory."""
    root = library.local(source['root'])
    managed = library.local(library.config()['managed_root'])
    if not root.is_dir():
        raise ValueError('스캔 경로가 디렉토리가 아닙니다.')
    if root.is_relative_to(managed) or root.is_relative_to(library.db):
        raise ValueError('관리 디렉토리 또는 DB를 소스로 스캔할 수 없습니다.')
    def failed(exc):
        raise exc
    for base, directories, files in os.walk(root, onerror=failed, followlinks=False):
        if check:
            check()
        directories[:] = sorted(d for d in directories if not (Path(base) / d).is_symlink() and not (Path(base) / d).resolve().is_relative_to(managed) and not (Path(base) / d).resolve().is_relative_to(library.db))
        for name in sorted(files):
            if check:
                check()
            path = Path(base) / name
            if not name.startswith('._') and path.suffix.lower() in EXTENSIONS and not path.is_symlink():
                resolved = library.local(path)
                if not resolved.is_relative_to(managed) and not resolved.is_relative_to(library.db):
                    yield resolved.as_uri(), {'path': str(resolved)}
        if not source.get('recursive', True):
            directories.clear()


class ScanPause(Exception):
    def __init__(self, status, warning):
        self.status, self.warning = status, warning
        super().__init__(warning)


def journal_records(path):
    """Recover a torn final JSONL line after a process/power interruption."""
    if not path.exists():
        return []
    values = []
    with path.open('rb+') as stream:
        while True:
            offset = stream.tell()
            line = stream.readline()
            if not line:
                break
            try:
                if not line.endswith(b'\n'):
                    raise ValueError('incomplete line')
                values.append(json.loads(line))
            except (ValueError, UnicodeDecodeError):
                if stream.read(1):
                    raise ValueError('스캔 저널 중간에 손상된 데이터가 있습니다.')
                stream.truncate(offset)
                break
    return values


class ScanEngine:
    def __init__(self, library, source_id, mode='incremental', full=False, progress=None, stopped=None):
        self.library = library
        self.source_id = component(source_id)
        self.mode = mode
        self.full = full or mode == 'restart'
        self.progress = progress or (lambda state: None)
        self.stopped = stopped or (lambda: False)
        self.last_flush = 0
        self.last_disk = 0
        self.state = {}

    def emit(self):
        self.state['updated_at'] = now()
        self.state['percent'] = round(self.state['processed'] * 100 / self.state['total'], 1) if self.state.get('inventory_complete') and self.state['total'] else (100 if self.state.get('inventory_complete') else None)
        self.progress(copy.deepcopy(self.state))

    def save(self):
        self.emit()
        atomic_json(self.folder / 'state.json', self.state)

    def flush(self, stream):
        stream.flush()
        os.fsync(stream.fileno())
        self.last_flush = time.monotonic()
        self.save()

    def check(self, extra=0, temporary=False, force=False, allow_stop=True):
        if allow_stop and self.stopped():
            raise ScanPause('stopped', '사용자 요청으로 중지했습니다. 저장한 위치부터 이어할 수 있습니다.')
        current = time.monotonic()
        if not force and current - self.last_disk < 1:
            return
        self.last_disk = current
        # Keep space for remaining journal records and publication, in addition to reserve.
        remaining = max(0, self.state.get('total', 0) - self.state.get('processed', 0))
        required = self.reserve + max(8 * MIB, remaining * RECORD_ESTIMATE) + extra
        free = shutil.disk_usage(self.library.db).free
        self.state['disk'] = {'free_bytes': free, 'required_bytes': required, 'reserve_bytes': self.reserve, 'path': str(self.library.db)}
        if free < required:
            raise ScanPause('paused_low_space', f'DB 디스크 공간 부족 예상: 여유 {free // MIB:,} MiB / 필요 {required // MIB:,} MiB. 공간을 확보한 뒤 이어하기를 실행하세요.')
        if temporary:
            free = shutil.disk_usage(tempfile.gettempdir()).free
            needed = self.reserve + max(MIB, extra)
            self.state['temporary_disk'] = {'free_bytes': free, 'required_bytes': needed, 'path': tempfile.gettempdir()}
            if free < needed:
                raise ScanPause('paused_low_space', f'원격 다운로드 임시 디스크 공간 부족: 여유 {free // MIB:,} MiB / 필요 {needed // MIB:,} MiB.')

    def local_files(self, source):
        yield from local_media_files(self.library, source, self.check)

    def process(self, source, uri, info, old):
        if old and old['lifecycle']['status'] not in {'active', 'source_unregistered'}:
            return None, 'ignored'
        location = {'source_id': self.source_id, 'role': 'source', 'protocol': source.get('protocol', 'file'), 'uri': uri,
                    'host': socket.gethostname() if 'path' in info else urlsplit(uri).hostname,
                    'location_type': 'local' if 'path' in info else 'remote', 'status': 'available', **info}
        def transfer(total, downloaded):
            self.check(extra=max(0, (total or (downloaded + 8 * MIB)) - downloaded), temporary=True, force=downloaded == 0)
        with self.library.materialize(location, transfer=transfer) as path:
            self.check(force=True)
            stat = path.stat()
            if not self.full and old and 'path' in info and old['size_bytes'] == stat.st_size and old.get('mtime_ns') == stat.st_mtime_ns:
                item = copy.deepcopy(old)
                item['last_seen_at'] = now()
                if item['lifecycle']['status'] == 'source_unregistered':
                    item['lifecycle'] = {'status': 'active'}
                for loc in item['locations']:
                    if loc.get('source_id') == self.source_id and loc['uri'] == uri:
                        loc['status'] = 'available'
                return item, 'unchanged'
            capture = metadata(path)
            self.check()
            if 'path' not in info:
                capture['filesystem_created_at'] = None
            if 'path' not in info and capture['date_basis'] in {'filesystem_modified_at', 'filesystem_created_at'}:
                from datetime import datetime
                from email.utils import parsedate_to_datetime
                value = info.get('modified')
                if value:
                    try:
                        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    except ValueError:
                        dt = parsedate_to_datetime(value)
                    capture.update(date_key=dt.strftime('%Y-%m-%d'), date_basis='remote_modified_at', filesystem_modified_at=dt.isoformat())
                else:
                    capture.update(date_key='unknown', date_basis='unknown', filesystem_modified_at=None)
            sha256 = digest(path, control=self.check)
            item = copy.deepcopy(old) if old else {'media_id': uid(), 'classification': {'category_id': source.get('category', 'family'), 'owner_id': source.get('owner_id', 'default'), 'person_ids': [], 'events': [], 'tags': []}, 'locations': [], 'lifecycle': {'status': 'active'}, 'revision': 0}
            if item['lifecycle']['status'] == 'source_unregistered':
                item['lifecycle'] = {'status': 'active'}
            changed = not old or old['sha256'] != sha256
            item.update(name=unquote(Path(urlsplit(uri).path).name), media_type='video' if path.suffix.lower() in VIDEO_EXTENSIONS else 'image', size_bytes=stat.st_size,
                        mtime_ns=stat.st_mtime_ns if 'path' in info else None, capture=capture, sha256=sha256, last_seen_at=now(), revision=item['revision'] + 1)
            item['locations'] = [location] + [loc for loc in item['locations'] if loc['role'] == 'managed']
            if changed:
                for loc in item['locations'][1:]:
                    loc['status'] = 'stale'
            return item, 'updated' if old else 'added'

    def apply_records(self, items, records):
        known_ids = {item['media_id']: item for item in items}
        for record in records:
            item = record.get('item')
            if not item:
                continue
            current = known_ids.get(item['media_id'])
            if current:
                # Edits/trash operations made while paused take precedence over journal copies.
                item = copy.deepcopy(item)
                item['classification'] = current['classification']
                item['lifecycle'] = {'status': 'active'} if current['lifecycle']['status'] == 'source_unregistered' else current['lifecycle']
                item['locations'] = [loc for loc in item['locations'] if loc['role'] == 'source'] + [loc for loc in current['locations'] if loc['role'] == 'managed']
                if current.get('sha256') != item['sha256']:
                    for loc in item['locations'][1:]:
                        loc['status'] = 'stale'
            known_ids[item['media_id']] = item
        return list(known_ids.values())

    def publish(self, records):
        items = self.apply_records(self.library.items(), records)
        # Do not consume the safety reserve while publishing a complete JSON generation.
        estimated = len(json.dumps(items, ensure_ascii=False).encode('utf-8')) * 3 + 2 * MIB
        if shutil.disk_usage(self.library.db).free < self.reserve + estimated:
            self.state['published'] = False
            return False
        if self.state['status'] == 'completed' and not self.state['errors']:
            seen = {entry['uri'] for entry in self.entries}
            for item in items:
                for location in item['locations']:
                    if location.get('source_id') == self.source_id and location['role'] == 'source' and location['uri'] not in seen:
                        location['status'] = 'missing'
        self.library.commit(items, control=lambda: self.check(force=True, allow_stop=self.state['status'] != 'stopped'))
        self.state['published'] = True
        return True

    def run(self):
        if self.mode not in {'incremental', 'restart', 'resume'}:
            raise ValueError('스캔 모드는 incremental, restart, resume 중 하나여야 합니다.')
        library = self.library
        with library.writing():
            config = library.config()
            source = next((s for s in config['sources'] if s['source_id'] == self.source_id), None)
            if not source:
                raise ValueError('저장소를 찾지 못했습니다.')
            self.reserve = int(config.get('scan_min_free_mb', 512)) * MIB
            directory = library.db / 'scans' / 'sessions'
            pointer = directory / (self.source_id + '.json')
            previous = read_json(pointer)
            if self.mode == 'resume':
                if not previous:
                    raise ValueError('이어할 스캔이 없습니다.')
                self.folder = directory / component(previous['scan_id'])
                self.state = read_json(self.folder / 'state.json')
                if not self.state or self.state['status'] == 'completed':
                    raise ValueError('이미 완료했거나 이어할 수 없는 스캔입니다.')
                if self.state['source'] != source:
                    raise ValueError('소스 설정이 변경되었습니다. 처음부터 다시 실행하세요.')
                self.full = self.state['full']
            else:
                self.folder = directory / uid()
                self.state = {'schema_version': 1, 'scan_id': self.folder.name, 'source_id': self.source_id, 'source': source,
                              'full': self.full, 'created_at': now(), 'inventory_complete': False, 'total': 0, 'processed': 0,
                              'added': 0, 'updated': 0, 'unchanged': 0, 'ignored': 0, 'errors': [], 'status': 'running', 'phase': 'listing', 'published': False}
                self.save()
                atomic_json(pointer, {'scan_id': self.folder.name})
            inventory_path = self.folder / 'inventory.jsonl'
            results_path = self.folder / 'results.jsonl'
            self.entries = journal_records(inventory_path)
            records = journal_records(results_path)
            self.state.update(total=len(self.entries), processed=len(records), status='running', warning=None)
            for key in ('added', 'updated', 'unchanged', 'ignored'):
                self.state[key] = sum(r['outcome'] == key for r in records)
            self.state['errors'] = [r['error'] for r in records if r.get('error')]
            self.save()
            try:
                self.check(force=True)
                if not self.state['inventory_complete']:
                    self.state['phase'] = 'listing'
                    seen = {e['uri'] for e in self.entries}
                    entries = self.local_files(source) if source.get('protocol', 'file') == 'file' else library.remote_files(source, control=self.check)
                    with inventory_path.open('ab') as inventory:
                        try:
                            for uri, info in entries:
                                self.check()
                                if uri in seen:
                                    continue
                                entry = {'uri': uri, 'info': info}
                                inventory.write((json.dumps(entry, ensure_ascii=False) + '\n').encode('utf-8'))
                                self.entries.append(entry)
                                seen.add(uri)
                                self.state['total'] = len(self.entries)
                                self.emit()
                                if len(self.entries) % 100 == 0 or time.monotonic() - self.last_flush > 1:
                                    self.flush(inventory)
                        finally:
                            self.flush(inventory)
                    self.state['inventory_complete'] = True
                    self.save()
                self.state['phase'] = 'processing'
                items = self.apply_records(library.items(), records)
                known = {loc['uri']: item for item in items for loc in item['locations'] if loc['role'] == 'source' and loc.get('source_id') == self.source_id}
                with results_path.open('ab') as results:
                    try:
                        for ordinal in range(len(records), len(self.entries)):
                            entry = self.entries[ordinal]
                            uri, info = entry['uri'], entry['info']
                            self.state['current_file'] = info.get('path', uri)
                            self.emit()
                            self.check(force=True)
                            try:
                                item, outcome = self.process(source, uri, info, known.get(uri))
                                record = {'ordinal': ordinal, 'outcome': outcome, 'item': item}
                                if item:
                                    known[uri] = item
                            except ScanPause:
                                raise
                            except OSError as exc:
                                if exc.errno in {errno.ENOSPC, getattr(errno, 'EDQUOT', errno.ENOSPC)}:
                                    raise ScanPause('paused_low_space', '디스크 쓰기 공간이 부족합니다. 공간 확보 후 이어하기를 실행하세요.') from exc
                                record = {'ordinal': ordinal, 'outcome': 'error', 'error': {'uri': uri, 'error': str(exc)}}
                            except Exception as exc:
                                record = {'ordinal': ordinal, 'outcome': 'error', 'error': {'uri': uri, 'error': str(exc)}}
                            results.write((json.dumps(record, ensure_ascii=False) + '\n').encode('utf-8'))
                            records.append(record)
                            self.state['published'] = False
                            self.state['processed'] = len(records)
                            if record['outcome'] == 'error':
                                self.state['errors'].append(record['error'])
                            else:
                                self.state[record['outcome']] += 1
                            self.emit()
                            if len(records) % 100 == 0 or time.monotonic() - self.last_flush > 1:
                                self.flush(results)
                    finally:
                        self.flush(results)
                self.state.update(status='completed', phase='publishing')
                self.emit()
                self.check(force=True)
                if not self.publish(records):
                    raise ScanPause('paused_low_space', '결과 저널은 저장했지만 월별 JSON을 발행할 공간이 부족합니다. 공간 확보 후 이어하기를 실행하세요.')
                self.state['phase'] = 'done'
            except ScanPause as exc:
                self.state.update(status=exc.status, warning=exc.warning)
                # The journal is the resume authority even if the disk cannot fit a new generation.
                if exc.status == 'stopped':
                    try:
                        if not self.publish(records):
                            self.state['warning'] += ' 처리 결과는 저널에 보존했으며 월별 JSON 발행은 공간 확보 후 이어하기에서 완료합니다.'
                    except ScanPause as disk:
                        self.state.update(status=disk.status, warning=disk.warning, published=False)
                    except Exception as failure:
                        self.state.update(status='paused_low_space' if isinstance(failure, OSError) and failure.errno in {errno.ENOSPC, getattr(errno, 'EDQUOT', errno.ENOSPC)} else 'failed', warning='진행 저널은 저장했습니다. 월별 JSON 발행 실패: ' + str(failure), published=False)
            except OSError as exc:
                self.state.update(status='paused_low_space' if exc.errno in {errno.ENOSPC, getattr(errno, 'EDQUOT', errno.ENOSPC)} else 'failed', warning=str(exc))
            except Exception as exc:
                self.state.update(status='failed', warning=str(exc))
            self.state['seen'] = len(self.entries)
            self.state['completed_at'] = now()
            self.save()
            atomic_json(library.db / 'scans' / (self.state['scan_id'] + '.json'), self.state)
            return copy.deepcopy(self.state)


def scan_sessions(library):
    directory = library.db / 'scans' / 'sessions'
    sessions = []
    for pointer in directory.glob('*.json'):
        value = read_json(pointer)
        state = read_json(directory / component(value['scan_id']) / 'state.json')
        if state:
            sessions.append(state)
    return sessions
