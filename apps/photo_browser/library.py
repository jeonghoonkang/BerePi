"""JSON backed media library. Originals are never moved or deleted."""
import base64
import copy
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import uuid
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote
from urllib.request import Request, urlopen
from xml.etree import ElementTree

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi'}
EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
LOCATION_FILE = '.photo-browser-location.json'


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return uuid.uuid4().hex


def read_json(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uid() + '.tmp')
    try:
        with temporary.open('w', encoding='utf-8') as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


PAIR_HISTORY = '.photo-browser-pair-history'


def pair_snapshot(config, db):
    """Only connection fields; never retain source credentials or URL tokens."""
    sources = []
    for source in config.get('sources', []):
        entry = {key: source[key] for key in
                 ('source_id', 'protocol', 'root', 'category', 'owner_id', 'recursive') if key in source}
        if entry.get('protocol') in {'http', 'webdav'} and entry.get('root'):
            parsed = urlsplit(entry['root'])
            host = parsed.hostname or ''
            if ':' in host:
                host = '[' + host + ']'
            if parsed.port:
                host += ':' + str(parsed.port)
            entry['root'] = parsed._replace(netloc=host, query='', fragment='').geturl()
        sources.append(entry)
    return {'pair_id': config.get('pair_id'), 'db': str(db),
            'managed_root': config.get('managed_root'), 'sources': sources}


@contextmanager
def pair_lock(root):
    # One lock per managed path, shared by different DBs and processes.
    name = hashlib.sha256(str(root).encode()).hexdigest()
    handle = (Path(tempfile.gettempdir()) / ('photo-pair-' + name + '.lock')).open('a+b')
    try:
        if os.name == 'nt':
            import msvcrt
            if handle.seek(0, os.SEEK_END) == 0:
                handle.write(b'0')
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        handle.close()


def write_library_locations(db, managed_root, config=None, new_pair=False, reason="verify", history_before=None):
    """Commit config and both pair records together, with crash recovery journal."""
    db, managed_root = Path(db).resolve(), Path(managed_root).resolve()
    journal = db / '.photo-browser-pair-pending.json'
    with pair_lock(managed_root):
        current = read_json(db / 'config.json', {})
        db_marker = read_json(db / LOCATION_FILE, {})
        managed_marker = read_json(managed_root / LOCATION_FILE, {})
        pending = read_json(journal)
        pair_id = (uid() if new_pair else
                   (pending['config']['pair_id'] if pending else None) or current.get('pair_id') or db_marker.get('pair_id') or uid())
        if not re.fullmatch(r'[0-9a-f]{32}', pair_id):
            raise ValueError('DB의 pair_id 형식이 올바르지 않습니다.')
        if not new_pair:
            for marker in (db_marker, managed_marker):
                if marker.get('pair_id') and marker['pair_id'] != pair_id:
                    raise ValueError('DB와 관리 폴더의 pair_id가 다릅니다. 다른 라이브러리의 폴더는 연결할 수 없습니다.')
            if managed_marker and not managed_marker.get('pair_id') and managed_marker.get('db') != str(db):
                raise ValueError('관리 폴더가 다른 DB에 연결되어 있습니다.')
        if pending:
            if pending['managed_root'] != str(managed_root):
                raise ValueError('완료하지 못한 경로 저장이 있습니다. 기존 설정으로 다시 시작하세요.')
            pair_id = pending['config']['pair_id']
            updated = pending['config']
            saved_at = pending['saved_at']
        else:
            updated = dict(current if config is None else config, managed_root=str(managed_root), pair_id=pair_id)
            unchanged = {k: v for k, v in updated.items() if k != 'pair_saved_at'} == {k: v for k, v in current.items() if k != 'pair_saved_at'}
            saved_at = current.get('pair_saved_at', now()) if unchanged else now()
        updated['pair_saved_at'] = saved_at
        writes = [(db / 'config.json', updated)]
        for folder in (db, managed_root):
            value = {'format': 'photo-browser-location', 'schema_version': 2,
                     'pair_id': pair_id, 'saved_at': saved_at,
                     'db': str(db), 'managed_root': str(managed_root)}
            for key, target in (('db', db), ('managed_root', managed_root)):
                try:
                    value[key + '_relative'] = os.path.relpath(target, folder)
                except ValueError:
                    value[key + '_relative'] = None
            writes.append((folder / LOCATION_FILE, value))
        history_exists = any((db / PAIR_HISTORY).glob('*.json'))
        if not pending and history_exists and all(read_json(path) == value for path, value in writes):
            return
        event = pending.get('history_event') if pending else None
        if event is None:
            event = {'schema_version': 1, 'event_id': uid(), 'recorded_at': now(),
                     'reason': reason,
                     'before': history_before if history_before is not None else (pair_snapshot(current, db_marker.get('db', db)) if current else None),
                     'after': pair_snapshot(updated, db)}
        name = event['recorded_at'].replace(':', '').replace('+', '_') + '-' + event['event_id'] + '.json'
        for folder in (db, managed_root):
            writes.append((folder / PAIR_HISTORY / name, event))
        # Journal first: a process interruption is completed on the next startup.
        atomic_json(journal, {'managed_root': str(managed_root), 'config': updated, 'saved_at': saved_at, 'history_event': event})
        originals = [(path, path.read_bytes() if path.exists() else None) for path, _ in writes]
        try:
            for path, value in writes:
                atomic_json(path, value)
        except BaseException:
            # Ordinary I/O failures leave the prior pair intact. Keep the journal
            # if rollback itself fails so a restart can finish the transaction.
            for path, content in originals:
                if content is None:
                    path.unlink(missing_ok=True)
                else:
                    temporary = path.with_name(path.name + '.rollback-' + uid())
                    temporary.write_bytes(content)
                    os.replace(temporary, path)
            journal.unlink(missing_ok=True)
            raise
        journal.unlink(missing_ok=True)



def digest(path, control=None):
    hasher = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            if control:
                control()
            hasher.update(block)
    return hasher.hexdigest()


def component(value):
    if not isinstance(value, str) or not re.fullmatch(r'[\w-]{1,80}', value) or value.upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
        raise ValueError('분류와 소유자 ID는 문자, 숫자, 밑줄, 하이픈만 사용하세요.')
    return value


def metadata(path):
    stat = path.stat()
    result = {'captured_at': None, 'date_key': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d'),
              'date_basis': 'filesystem_modified_at', 'location': None,
              'filesystem_modified_at': datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
              'filesystem_created_at': datetime.fromtimestamp(stat.st_birthtime, timezone.utc).isoformat() if hasattr(stat, 'st_birthtime') else None,
              'width': None, 'height': None, 'duration_seconds': None, 'metadata_errors': []}
    if hasattr(stat, 'st_birthtime'):
        result.update(date_key=datetime.fromtimestamp(stat.st_birthtime).strftime('%Y-%m-%d'), date_basis='filesystem_created_at')
    try:
        if path.suffix.lower() in VIDEO_EXTENSIONS:
            probe = subprocess.run(['ffprobe', '-v', 'quiet', '-show_format', '-show_streams', '-of', 'json', str(path)], capture_output=True, text=True, timeout=30, check=True)
            data = json.loads(probe.stdout)
            tags = data.get('format', {}).get('tags', {})
            gps = re.match(r'([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)', tags.get('location') or tags.get('com.apple.quicktime.location.ISO6709', ''))
            if gps:
                result['location'] = {'latitude': float(gps[1]), 'longitude': float(gps[2]), 'source': 'video.location'}
            value = tags.get('creation_time')
            if value:
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                result.update(captured_at=dt.isoformat(), date_key=dt.strftime('%Y-%m-%d'), date_basis='video.creation_time')
            result['duration_seconds'] = float(data.get('format', {}).get('duration', 0))
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    result.update(width=stream.get('width'), height=stream.get('height'))
                    break
        else:
            from PIL import Image
            with Image.open(path) as image:
                result.update(width=image.width, height=image.height)
                exif = image.getexif()
                detail = exif.get_ifd(34665) if 34665 in exif else {}
                value = detail.get(36867) or exif.get(36867)
                if value:
                    dt = datetime.strptime(str(value), '%Y:%m:%d %H:%M:%S')
                    offset = detail.get(36881)
                    if offset:
                        dt = datetime.fromisoformat(dt.isoformat() + str(offset))
                    result.update(captured_at=dt.isoformat(), date_key=dt.strftime('%Y-%m-%d'), date_basis='exif.DateTimeOriginal', timezone_status='embedded' if offset else 'unknown')
                gps = exif.get_ifd(34853) if 34853 in exif else {}
                if 2 in gps and 4 in gps:
                    def degrees(v):
                        return float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
                    result['location'] = {'latitude': degrees(gps[2]) * (-1 if gps.get(1) == 'S' else 1), 'longitude': degrees(gps[4]) * (-1 if gps.get(3) == 'W' else 1), 'source': 'exif.GPS'}
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        result['metadata_errors'].append(str(exc))
    return result


class Library:
    def __init__(self, db, boundary):
        self.db = Path(db).resolve()
        self.boundary = Path(boundary).resolve()
        self.db.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.lookup_lock = threading.Lock()
        self.lookup_generation = None
        self.lookup_chunks = {}
        self.facets_lock = threading.Lock()
        self.facets_generation = None
        self.facets_cache = None
        # Validate/migrate the pair and complete interrupted path commits on startup.
        pending = read_json(self.db / '.photo-browser-pair-pending.json')
        config = pending['config'] if pending else read_json(self.db / 'config.json',
                    {'schema_version': 1, 'managed_root': str(self.db.parent / 'library'), 'sources': []})
        root = Path(config['managed_root']).expanduser().resolve()
        if not root.is_relative_to(self.boundary) or root == self.boundary or (
                root.is_relative_to(self.db) or self.db.is_relative_to(root)):
            raise ValueError('관리 디렉토리는 허용 루트 안에서 DB와 분리된 경로여야 합니다.')
        with self.writing():
            write_library_locations(self.db, root, config=config, reason="startup")

    @contextmanager
    def writing(self):
        with self.lock:
            lockfile = self.db / '.write.lock'
            handle = lockfile.open('a+b')
            try:
                if os.name == 'nt':
                    import msvcrt
                    if handle.seek(0, os.SEEK_END) == 0:
                        handle.write(b'0')
                        handle.flush()
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                handle.close()
                raise ValueError('다른 작업이 실행 중입니다.') from exc
            try:
                yield
            finally:
                if os.name == 'nt':
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                handle.close()

    def local(self, value):
        path = Path(value).expanduser().resolve()
        if not path.is_relative_to(self.boundary):
            raise ValueError(f'허용된 루트 디렉토리 밖입니다.\n허용된 루트 디렉토리: {self.boundary}')
        return path

    def config(self):
        return read_json(self.db / 'config.json')

    def pair_history(self, limit=100):
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError('limit는 1~1000이어야 합니다.')
        paths = sorted((self.db / PAIR_HISTORY).glob('*.json'), reverse=True)
        entries, errors = [], []
        for path in paths[:limit]:
            try:
                entries.append(read_json(path))
            except (OSError, ValueError, UnicodeError) as exc:
                errors.append({'file': path.name, 'error': str(exc)})
        return {'items': entries, 'total': len(paths), 'errors': errors}

    def save_config(self, config):
        with self.writing():
            if not isinstance(config.get('managed_root'), str) or not isinstance(config.get('sources', []), list):
                raise ValueError('managed_root 문자열과 sources 목록이 필요합니다.')
            root = self.local(config['managed_root'])
            old_root = Path(self.config()['managed_root']).expanduser().resolve()
            if root != old_root and any(l['role'] == 'managed' for i in self.items() for l in i['locations']):
                raise ValueError('관리 복사본이 있는 경로는 변경할 수 없습니다. 별도 라이브러리 DB를 사용하세요.')
            if root == self.boundary or root == self.db or self.db.is_relative_to(root) or root.is_relative_to(self.db):
                raise ValueError('관리 디렉토리는 루트 또는 DB와 분리된 하위 경로를 지정하세요.')
            ids = set()
            roots = {}
            for source in config.get('sources', []):
                if not isinstance(source, dict) or not isinstance(source.get('root'), str):
                    raise ValueError('소스에는 경로 문자열이 필요합니다.')
                source['source_id'] = component(source['source_id'])
                component(source.get('category', 'family'))
                component(source.get('owner_id', 'default'))
                if source['source_id'] in ids:
                    raise ValueError('저장소 ID가 중복됩니다.')
                ids.add(source['source_id'])
                protocol = source.get('protocol', 'file')
                if protocol == 'file':
                    source['root'] = str(self.local(source['root']))
                elif protocol in {'webdav', 'http'}:
                    parsed = urlsplit(source['root'])
                    if parsed.scheme not in {'http', 'https'} or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
                        raise ValueError('원격 경로는 인증정보·쿼리 없는 HTTP(S) URL이어야 합니다.')
                else:
                    raise ValueError('지원하지 않는 프로토콜입니다.')
                key = self.source_key(source)
                if key in roots:
                    raise ValueError(f'같은 경로가 이미 등록되어 있습니다. 기존 소스 ID: {roots[key]}')
                roots[key] = source['source_id']
            minimum = config.get('scan_min_free_mb', 512)
            if isinstance(minimum, bool) or not isinstance(minimum, int) or not 32 <= minimum <= 1048576:
                raise ValueError('스캔 디스크 여유 기준은 32~1,048,576 MiB 정수여야 합니다.')
            write_library_locations(self.db, root, config={'schema_version': 1, 'managed_root': str(root), 'sources': config.get('sources', []), 'scan_min_free_mb': minimum}, reason='settings_changed')
            if root != old_root and old_root.is_relative_to(self.boundary):
                old_marker = old_root / LOCATION_FILE
                try:
                    previous = read_json(old_marker, {})
                    if isinstance(previous, dict) and previous.get('format') == 'photo-browser-location' and previous.get('db') == str(self.db):
                        old_marker.unlink()
                except (ValueError, UnicodeError):
                    pass

    def apply_source_classification(self, source_id):
        source_id = component(source_id)
        with self.writing():
            source = next((s for s in self.config()['sources'] if s['source_id'] == source_id), None)
            if source is None:
                raise ValueError('소스를 찾지 못했습니다.')
            category = component(source.get('category', 'family'))
            owner = component(source.get('owner_id', 'default'))
            items = self.items()
            matched = updated = 0
            for item in items:
                if item['lifecycle']['status'] != 'active' or not any(
                    loc['role'] == 'source' and loc.get('source_id') == source_id for loc in item['locations']
                ):
                    continue
                matched += 1
                classification = item['classification']
                if classification['category_id'] != category or classification['owner_id'] != owner:
                    classification.update(category_id=category, owner_id=owner)
                    item['revision'] += 1
                    updated += 1
            if updated:
                self.commit(items)
            return dict(source_id=source_id, category_id=category, owner_id=owner,
                        matched=matched, updated=updated, unchanged=matched - updated,
                        warning='기존 관리 복사본은 이동하지 않았습니다. 병합 정보를 갱신해 새 출력 경로를 확인하세요.')

    def duplicate_sources(self):
        config = self.config()
        sources = {source['source_id']: source for source in config['sources']}
        files = {source_id: {} for source_id in sources}
        manifest = read_json(self.db / 'index.json', {'chunks': []})
        for chunk in manifest['chunks']:
            for item in read_json(self.db / chunk['path'])['items']:
                if item['lifecycle']['status'] != 'active':
                    continue
                for location in item['locations']:
                    source_id = location.get('source_id')
                    if location['role'] != 'source' or source_id not in sources or location.get('status') in {'missing', 'inactive'}:
                        continue
                    source = sources[source_id]
                    try:
                        if source.get('protocol', 'file') == 'file':
                            relative = Path(location['path']).relative_to(Path(source['root'])).as_posix()
                        else:
                            base = unquote(urlsplit(source['root']).path).rstrip('/') + '/'
                            path = unquote(urlsplit(location['uri']).path)
                            if not path.startswith(base):
                                continue
                            relative = path[len(base):]
                    except (KeyError, ValueError):
                        continue
                    files[source_id][relative] = (item['size_bytes'], item['sha256'])
        grouped = defaultdict(list)
        for source_id, entries in files.items():
            if not entries:
                continue
            listing = sorted((path, size) for path, (size, sha) in entries.items())
            fingerprint = hashlib.sha256(json.dumps(listing, ensure_ascii=False).encode()).hexdigest()
            content = hashlib.sha256(json.dumps(sorted((path, size, sha) for path, (size, sha) in entries.items()), ensure_ascii=False).encode()).hexdigest()
            grouped[fingerprint].append({'source_id': source_id, 'root': sources[source_id]['root'],
                                         'content_fingerprint': content})
        groups = []
        for fingerprint, members in grouped.items():
            if len(members) < 2:
                continue
            entries = files[members[0]['source_id']]
            groups.append({'fingerprint': fingerprint, 'sources': members, 'file_count': len(entries),
                           'total_bytes': sum(value[0] for value in entries.values()),
                           'same_content': len({member['content_fingerprint'] for member in members}) == 1,
                           'files': [{'relative_path': path, 'size_bytes': value[0]} for path, value in sorted(entries.items())]})
        return {'groups': groups, 'basis': '스캔된 활성 파일의 상대 경로·개별 크기 비교. 실제 디스크를 다시 읽지 않으며 해시는 마지막 스캔 값입니다.'}

    def unregister_duplicate_source(self, source_id, keep_id, fingerprint):
        with self.writing():
            if source_id == keep_id:
                raise ValueError('유지할 소스와 해제할 소스가 같을 수 없습니다.')
            groups = self.duplicate_sources()['groups']
            if not any(group['fingerprint'] == fingerprint and {source_id, keep_id}.issubset(
                {source['source_id'] for source in group['sources']}) for group in groups):
                raise ValueError('중복 비교 결과가 변경됐습니다. 다시 검색하세요.')
            config = self.config()
            root = self.local(config['managed_root'])
            items = self.items()
            selected = [item for item in items if item['lifecycle']['status'] == 'active' and any(
                loc['role'] == 'source' and loc.get('source_id') == source_id for loc in item['locations'])]
            exclusive = {item['media_id'] for item in selected if not any(
                loc['role'] == 'source' and loc.get('source_id') != source_id for loc in item['locations'])}
            protected = {str(self.local(loc['path'])) for item in items for loc in item['locations']
                         if loc.get('path') and (loc['role'] == 'source' or item['media_id'] not in exclusive)}
            candidates = {str(self.local(loc['path'])) for item in selected if item['media_id'] in exclusive
                          for loc in item['locations'] if loc['role'] == 'managed'}
            removable = candidates - protected
            for value in removable:
                path = Path(value)
                if not path.is_relative_to(root) or path.is_relative_to(root / '.trash') or path == root:
                    raise ValueError('관리 디렉토리 내부의 복사본만 삭제할 수 있습니다.')
            cleanup_id = uid()
            record_path = self.db / 'source_cleanup' / (cleanup_id + '.json')
            record = {'cleanup_id': cleanup_id, 'source_id': source_id, 'keep_id': keep_id,
                      'status': 'deleting', 'created_at': now(), 'items_before': copy.deepcopy(selected),
                      'candidates': sorted(removable)}
            atomic_json(record_path, record)
            deleted, errors = set(), []
            # Original locations and shared managed files are excluded above.
            # Keep a durable log so interrupted cleanup can be inspected.
            log_path = record_path.with_suffix('.jsonl')
            with log_path.open('a', encoding='utf-8') as log:
                for value in sorted(removable):
                    try:
                        Path(value).unlink(missing_ok=True)
                        deleted.add(value)
                        outcome = {'path': value, 'status': 'deleted'}
                    except OSError as exc:
                        outcome = {'path': value, 'status': 'error', 'error': str(exc)}
                        errors.append(outcome)
                    log.write(json.dumps(outcome, ensure_ascii=False) + '\n')
                    log.flush()
                    os.fsync(log.fileno())
            for item in selected:
                item['locations'] = [loc for loc in item['locations'] if not (
                    loc['role'] == 'managed' and str(self.local(loc['path'])) in deleted)]
                if not errors and item['media_id'] in exclusive:
                    item['lifecycle']['status'] = 'source_unregistered'
            self.commit(items)
            if not errors:
                config['sources'] = [source for source in config['sources'] if source['source_id'] != source_id]
                write_library_locations(self.db, config['managed_root'], config=config, reason='sources_changed')
            record.update(status='partial_failure' if errors else 'completed', deleted_files=len(deleted),
                          retained_shared_files=len(candidates & protected), errors=errors)
            atomic_json(record_path, record)
            return {'removed_source_id': None if errors else source_id, 'kept_source_id': keep_id,
                    'deleted_managed_files': len(deleted), 'retained_shared_files': len(candidates & protected),
                    'errors': errors, 'cleanup_id': cleanup_id,
                    'warning': ('일부 관리 파일을 삭제하지 못해 소스 등록은 유지했습니다. 결과의 오류를 확인하세요.' if errors else
                                '소스 등록과 전용 관리 복사본을 정리했습니다. 원본 파일과 공유 관리 파일은 유지했습니다.')}

    def source_key(self, source):
        protocol = source.get('protocol', 'file')
        if protocol == 'file':
            return protocol, str(self.local(source['root']))
        parsed = urlsplit(source['root'])
        return protocol, (parsed.scheme.lower(), parsed.netloc.lower(), unquote(parsed.path).rstrip('/'))

    def rename_source(self, old, new):
        old, new = component(old), component(new)
        with self.writing():
            config = self.config()
            source = next((s for s in config['sources'] if s['source_id'] == old), None)
            if not source:
                raise ValueError('기존 소스를 찾지 못했습니다.')
            if old == new:
                return config
            if any(s['source_id'] == new for s in config['sources']):
                raise ValueError('이미 사용 중인 소스 ID입니다.')
            def replace(value):
                if isinstance(value, dict):
                    return {k: new if k == 'source_id' and v == old else replace(v) for k, v in value.items()}
                if isinstance(value, list):
                    return [replace(v) for v in value]
                return value
            items = replace(self.items())
            # Resume journals contain media locations as well as the source snapshot.
            scans = self.db / 'scans'
            for path in scans.rglob('*.json'):
                atomic_json(path, replace(read_json(path)))
            for path in scans.rglob('*.jsonl'):
                temporary = path.with_name(path.name + '.rename.tmp')
                try:
                    with path.open(encoding='utf-8') as reader, temporary.open('w', encoding='utf-8') as writer:
                        for line in reader:
                            try:
                                record = json.loads(line)
                            except json.JSONDecodeError:
                                break  # Ignore an incomplete trailing journal record.
                            writer.write(json.dumps(replace(record), ensure_ascii=False) + '\n')
                    os.replace(temporary, path)
                finally:
                    temporary.unlink(missing_ok=True)
            pointer = scans / 'sessions' / (old + '.json')
            if pointer.exists():
                os.replace(pointer, pointer.with_name(new + '.json'))
            self.commit(items)
            source['source_id'] = new
            write_library_locations(self.db, config['managed_root'], config=config, reason='sources_changed')
            return config

    def item(self, media_id):
        """Resolve one item without materializing the complete media collection.

        Chunk generations are immutable. Serialize index construction so concurrent
        image requests share one small ID-to-chunk map instead of decoding the
        entire collection independently.
        """
        with self.lookup_lock:
            manifest = read_json(self.db / 'index.json', {'chunks': []})
            generation = tuple(entry['path'] for entry in manifest['chunks'])
            if generation != self.lookup_generation:
                chunks = {}
                for relative in generation:
                    for item in read_json(self.db / relative)['items']:
                        chunks[item['media_id']] = relative
                self.lookup_chunks = chunks
                self.lookup_generation = generation
            relative = self.lookup_chunks.get(media_id)
            if relative is None:
                return None
            return next((item for item in read_json(self.db / relative)['items']
                         if item['media_id'] == media_id), None)

    def facets(self):
        # Old databases are read one immutable chunk at a time, once per generation.
        # New manifests contain the active-item summary directly.
        with self.facets_lock:
            manifest = read_json(self.db / 'index.json', {'chunks': []})
            if 'active_facets' in manifest:
                return manifest['active_facets']
            generation = tuple(chunk['path'] for chunk in manifest['chunks'])
            if generation != self.facets_generation:
                values = {key: set() for key in ('events', 'tags', 'person_ids', 'category_id', 'owner_id')}
                for chunk in manifest['chunks']:
                    for item in read_json(self.db / chunk['path'])['items']:
                        if item['lifecycle']['status'] != 'active':
                            continue
                        for key in values:
                            value = item['classification'][key]
                            values[key].update(value if isinstance(value, list) else [value])
                self.facets_cache = {key: sorted(value) for key, value in values.items()}
                self.facets_generation = generation
            return self.facets_cache

    def items(self, filters=None):
        manifest = read_json(self.db / 'index.json', {'chunks': []})
        chunks = manifest['chunks']
        if filters:
            for argument, key in [('event', 'events'), ('tag', 'tags'), ('person', 'person_ids'), ('category', 'category_id'), ('owner', 'owner_id')]:
                if filters.get(argument):
                    chunks = [c for c in chunks if filters[argument] in c.get('facets', {}).get(key, [filters[argument]])]
            if filters.get('from'):
                chunks = [c for c in chunks if c['last_date'] >= filters['from']]
            if filters.get('to'):
                chunks = [c for c in chunks if c['first_date'] <= filters['to']]
        return [item for entry in chunks for item in read_json(self.db / entry['path'])['items']]

    def commit(self, items, control=None):
        # Immutable generations + atomic manifest: readers never see half-written chunks.
        generation = uid()
        groups = defaultdict(list)
        for item in items:
            c = item['classification']
            date = item['capture']['date_key']
            year, month = (date[:4], date[5:7]) if date != 'unknown' else ('unknown', 'unknown')
            groups[f"{component(c['category_id'])}/{component(c['owner_id'])}/{year}/{month}"].append(item)
        chunks = []
        for group, values in sorted(groups.items()):
            if control:
                control()
            values.sort(key=lambda x: (x['capture']['date_key'], x['media_id']))
            for offset in range(0, len(values), 100):
                if control:
                    control()
                relative = f'media/{group}/media_{generation}_{offset // 100 + 1:06d}.json'
                page = values[offset:offset + 100]
                atomic_json(self.db / relative, {'schema_version': 1, 'items': page, 'item_count': len(page)})
                facets = {}
                for key in ('events', 'tags', 'person_ids', 'category_id', 'owner_id'):
                    facets[key] = sorted({value for item in page for value in (item['classification'][key] if isinstance(item['classification'][key], list) else [item['classification'][key]])})
                chunks.append({'path': relative, 'count': len(page), 'first_date': page[0]['capture']['date_key'], 'last_date': page[-1]['capture']['date_key'], 'facets': facets})
        exact, candidates = defaultdict(list), defaultdict(list)
        for item in items:
            if item['lifecycle']['status'] != 'active':
                continue
            exact[item['sha256']].append(item['media_id'])
            capture = item['capture']
            if capture.get('captured_at') and capture.get('location'):
                gps = capture['location']
                candidates[(capture['captured_at'], round(gps['latitude'], 4), round(gps['longitude'], 4))].append(item['media_id'])
        duplicate_path = f'duplicates/{generation}.json'
        if control:
            control()
        atomic_json(self.db / duplicate_path, {'schema_version': 1, 'exact': [{'sha256': key, 'members': ids} for key, ids in exact.items() if len(ids) > 1], 'candidates': [{'reason': 'same_capture_time_and_nearby_gps', 'members': ids} for ids in candidates.values() if len(ids) > 1]})
        if control:
            control()
        active_facets = {key: set() for key in ('events', 'tags', 'person_ids', 'category_id', 'owner_id')}
        for item in items:
            if item['lifecycle']['status'] != 'active':
                continue
            for key in active_facets:
                value = item['classification'][key]
                active_facets[key].update(value if isinstance(value, list) else [value])
        active_facets = {key: sorted(value) for key, value in active_facets.items()}
        atomic_json(self.db / 'index.json', {'schema_version': 1, 'updated_at': now(), 'chunks': chunks, 'count': len(items), 'duplicates': duplicate_path, 'active_facets': active_facets})
        atomic_json(self.db / 'duplicates' / 'latest.json', {'generation_file': duplicate_path})
        # Old generations are retained for crash recovery; maintenance can remove them offline.

    def duplicates(self):
        index = read_json(self.db / 'index.json', {})
        return read_json(self.db / index['duplicates']) if index.get('duplicates') else {'exact': [], 'candidates': []}

    def remote_open(self, source, url, method='GET', headers=None):
        root = urlsplit(source['root'])
        target = urlsplit(url)
        prefix = unquote(root.path).rstrip('/') + '/'
        decoded = unquote(target.path)
        if target.scheme != root.scheme or target.netloc != root.netloc or (decoded != root.path and not decoded.startswith(prefix)) or '..' in decoded.split('/') or target.username or target.password or target.query or target.fragment:
            raise ValueError('원격 저장소 경계 밖의 URL입니다.')
        headers = dict(headers or {})
        credential = source.get('credential_ref')
        if credential:
            user = os.environ.get(credential + '_USER', '')
            password = os.environ.get(credential + '_PASSWORD', '')
            headers['Authorization'] = 'Basic ' + base64.b64encode(f'{user}:{password}'.encode()).decode()
        # Reject redirects so credentials and file reads stay inside the configured source.
        from urllib.request import HTTPRedirectHandler, build_opener
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        return build_opener(NoRedirect).open(Request(url, method=method, headers=headers), timeout=60)

    def remote_files(self, source, control=None):
        if control:
            control()
        if source['protocol'] == 'http':
            # Explicit manifest, never scrape arbitrary HTML directory listings.
            with self.remote_open(source, source['root'].rstrip('/') + '/manifest.json') as response:
                listing = json.load(response)
            for entry in listing['files']:
                if control:
                    control()
                url = urljoin(source['root'].rstrip('/') + '/', entry['path'])
                if Path(urlsplit(url).path).suffix.lower() in EXTENSIONS and not Path(unquote(urlsplit(url).path)).name.startswith('._'):
                    yield url, entry
        else:
            pending, seen = [source['root'].rstrip('/') + '/'], set()
            while pending:
                if control:
                    control()
                folder = pending.pop()
                if folder in seen:
                    continue
                seen.add(folder)
                with self.remote_open(source, folder, 'PROPFIND', {'Depth': '1'}) as response:
                    xml = ElementTree.fromstring(response.read())
                for entry in xml.findall('{DAV:}response'):
                    if control:
                        control()
                    href = entry.findtext('{DAV:}href')
                    if not href:
                        continue
                    url = urljoin(folder, href)
                    propstat = next((p for p in entry.findall('{DAV:}propstat') if ' 200 ' in p.findtext('{DAV:}status', '')), None)
                    if propstat is None:
                        continue
                    prop = propstat.find('{DAV:}prop')
                    if prop is None:
                        continue
                    if prop.find('.//{DAV:}collection') is not None:
                        if source.get('recursive', True) and url.rstrip('/') != folder.rstrip('/'):
                            pending.append(url.rstrip('/') + '/')
                    elif Path(urlsplit(url).path).suffix.lower() in EXTENSIONS and not Path(unquote(urlsplit(url).path)).name.startswith('._'):
                        yield url, {'modified': prop.findtext('{DAV:}getlastmodified'), 'size': prop.findtext('{DAV:}getcontentlength')}

    @contextmanager
    def materialize(self, location, transfer=None):
        if location['protocol'] == 'file':
            yield self.local(location['path'])
        else:
            source = next(s for s in self.config()['sources'] if s['source_id'] == location['source_id'])
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / ('media' + Path(urlsplit(location['uri']).path).suffix)
                with self.remote_open(source, location['uri']) as response, path.open('wb') as output:
                    if transfer:
                        total = response.headers.get('Content-Length')
                        total = int(total) if total and total.isdigit() else None
                        downloaded = 0
                        transfer(total, downloaded)
                        while True:
                            transfer(total, downloaded)
                            block = response.read(1024 * 1024)
                            if not block:
                                break
                            output.write(block)
                            downloaded += len(block)
                    else:
                        shutil.copyfileobj(response, output)
                yield path

    def scan(self, source_id, full=False, mode='incremental', progress=None, stopped=None):
        from scan_engine import ScanEngine
        return ScanEngine(self, source_id, mode, full, progress, stopped).run()

    def edit(self, ids, changes):
        with self.writing():
            items = self.items()
            for item in items:
                if item['media_id'] in ids:
                    for key in ('events', 'tags', 'person_ids'):
                        if key in changes:
                            values = changes[key]
                            if not isinstance(values, list) or len(values) > 100 or any(not isinstance(v, str) or not v.strip() or len(v) > 200 for v in values):
                                raise ValueError('분류 값은 200자 이하 문자열 목록이어야 합니다.')
                            item['classification'][key] = list(dict.fromkeys(v.strip() for v in values))
                    for key in ('category_id', 'owner_id'):
                        if key in changes:
                            item['classification'][key] = component(changes[key])
                    item['revision'] += 1
            self.commit(items)

    def merge_target(self, root, item):
        c, date = item['classification'], item['capture']['date_key']
        year, month = (date[:4], date[5:7]) if date != 'unknown' else ('unknown', 'unknown')
        name = item['name']
        if not name or name in {'.', '..'} or '/' in name or '\\' in name:
            raise ValueError('유효하지 않은 원본 파일명입니다.')
        target = root / component(c['category_id']) / component(c['owner_id']) / year / month / name
        if not target.resolve().is_relative_to(root):
            raise ValueError('관리 경로 밖입니다.')
        return target

    def resolve_merge_target(self, root, item, reserved, hashes, on_compare=None):
        """Choose the same non-destructive path for preview, capacity check and copy."""
        original = self.merge_target(root, item)
        number = 0
        while True:
            suffix = '' if number == 0 else ('_중복' if number == 1 else f'_중복_{number}')
            candidate = original.with_name(original.stem + suffix + original.suffix)
            if not candidate.parent.resolve().is_relative_to(root):
                raise ValueError('관리 경로 밖입니다.')
            key = os.path.normcase(str(candidate.absolute()))
            # Never reuse or replace a symlink, directory or other non-regular entry.
            if candidate.is_symlink() or (candidate.exists() and not candidate.is_file()):
                number += 1
                continue
            if candidate.exists():
                if on_compare:
                    on_compare(candidate)
                stat = candidate.stat()
                signature = (key, stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
                if signature not in hashes:
                    hashes[signature] = digest(candidate)
                if hashes[signature] != item['sha256']:
                    number += 1
                    continue
            if key in reserved and reserved[key] != item['sha256']:
                number += 1
                continue
            reserved[key] = item['sha256']
            return candidate

    @staticmethod
    def publish_merge_copy(temporary, target):
        """Publish verified bytes without ever replacing an existing filename."""
        try:
            os.link(temporary, target)
        except FileExistsError:
            raise
        except OSError:
            # FAT/exFAT and some remote filesystems do not support hard links.
            # Exclusive creation still prevents a late-arriving file being overwritten.
            with target.open('xb') as output:
                try:
                    with temporary.open('rb') as source:
                        shutil.copyfileobj(source, output)
                except BaseException:
                    output.close()
                    target.unlink(missing_ok=True)
                    raise
            shutil.copystat(temporary, target)

    def merge_space(self, root, items, pending, progress):
        targets = {}
        reserved, hashes = {}, {}
        for index, item in enumerate(pending):
            source = item['locations'][0]
            def checking(path, role='comparison_target', action='comparing_existing'):
                progress({'phase': 'checking_space', 'checked': index, 'check_total': len(pending),
                          'processed': 0, 'inventory_complete': False, 'current_file': str(path),
                          'current_file_role': role, 'current_action': action,
                          'source_file': source.get('path') or source.get('uri'), 'target_file': str(path)})
            target = self.resolve_merge_target(root, item, reserved, hashes, on_compare=checking)
            if not target.exists():
                key = str(target.resolve())
                targets[key] = max(targets.get(key, 0), item['size_bytes'])
            if index % 100 == 0:
                progress({'phase': 'checking_space', 'checked': index + 1, 'check_total': len(pending),
                          'processed': 0, 'inventory_complete': False, 'current_file': str(target),
                          'current_file_role': 'merge_destination', 'current_action': 'checking_space',
                          'source_file': source.get('path') or source.get('uri'), 'target_file': str(target)})
        # Each checkpoint retains a new immutable DB generation. Include their
        # cumulative growth, reports and a reserve, rather than only image bytes.
        generation_bytes = sum(len(json.dumps(item, ensure_ascii=False, indent=2).encode('utf-8')) + 4096 for item in items)
        db_bytes = generation_bytes * ((len(pending) + 24) // 25 + 3)
        reserve = self.config().get('scan_min_free_mb', 512) * 1048576
        volumes = {}
        def add(path, amount, role):
            existing = path
            while not existing.exists():
                existing = existing.parent
            device = existing.stat().st_dev
            if device not in volumes:
                volumes[device] = {'path': str(existing), 'free_bytes': shutil.disk_usage(existing).free,
                                   'required_bytes': reserve, 'reserve_bytes': reserve, 'roles': []}
            volumes[device]['required_bytes'] += amount
            volumes[device]['roles'].append(role)
        add(root, sum(targets.values()), '관리 복사본')
        add(self.db, db_bytes, 'DB·체크포인트·작업 기록 예상 증가량')
        remote_bytes = max((item['size_bytes'] for item in pending if item['locations'][0]['protocol'] != 'file'), default=0)
        if remote_bytes:
            add(Path(tempfile.gettempdir()), remote_bytes, '원격 파일 임시 다운로드')
        checks = list(volumes.values())
        return {'copy_bytes': sum(targets.values()), 'copy_files': len(targets),
                'db_estimated_bytes': db_bytes, 'volumes': checks,
                'ok': all(v['free_bytes'] >= v['required_bytes'] for v in checks)}

    def merge(self, ids=None, preview=False, progress=None, stopped=None, resume=None):
        with self.writing():
            if preview:
                return self._merge(ids, True, progress, stopped, resume)
            from merge_history import MergeHistory, first_merge_start
            root = self.local(self.config()['managed_root'])
            write_library_locations(self.db, root)
            run_started_at = now()
            merge_started_at = first_merge_start(self, resume, run_started_at) if resume else run_started_at
            original_progress = progress or (lambda state: None)
            def timed_progress(state):
                original_progress({**state, 'merge_started_at': merge_started_at, 'run_started_at': run_started_at})
            history = MergeHistory(self, root, resume, timed_progress)
            history.merge_started_at = merge_started_at
            try:
                result = self._merge(ids, False, timed_progress, stopped, resume, history)
            except BaseException as exc:
                try:
                    history.finish({'status': 'interrupted' if isinstance(exc, (KeyboardInterrupt, SystemExit)) else 'failed', 'warning': str(exc)})
                except Exception:
                    pass  # Preserve the original failure; the initial report may remain running.
                raise
            try:
                result['history_report'] = history.finish(result)
            except Exception as exc:
                result['history_report_error'] = str(exc)
                result['warning'] = (result.get('warning', '') + '\n병합 보고서 저장 실패: ' + str(exc)).strip()
            result.update(merge_started_at=merge_started_at, run_started_at=run_started_at)
            if result.get('plan_id'):
                atomic_json(self.db / 'plans' / (result['plan_id'] + '.json'), result)
            return result

    def _merge(self, ids=None, preview=False, progress=None, stopped=None, resume=None, history=None):
        progress = progress or (lambda state: None)
        progress({'phase': 'loading', 'inventory_complete': False, 'processed': 0})
        items = self.items()
        root = self.local(self.config()['managed_root'])
        stopped = stopped or (lambda: False)
        session_path = self.db / 'merges' / ((history.merge_id if history else component(resume) if resume else uid()) + '.json')
        if resume:
            if preview or not session_path.exists():
                raise ValueError('이어갈 병합 작업이 없습니다.')
            state = read_json(session_path)
            if state['managed_root'] != str(root):
                raise ValueError('관리 경로가 변경되어 이어갈 수 없습니다.')
        else:
            state = {'merge_id': session_path.stem, 'managed_root': str(root),
                     'ids': [i['media_id'] for i in items if i['lifecycle']['status'] == 'active' and (not ids or i['media_id'] in ids)],
                     'operations': [], 'status': 'running'}
        operations = state['operations']
        for key in ('current_file', 'current_file_role', 'current_action', 'source_file', 'target_file'):
            state.pop(key, None)
        completed = {op['media_id'] for op in operations}
        wanted = set(state['ids'])
        if history:
            state['merge_started_at'] = history.merge_started_at
            state['run_started_at'] = history.data['started_at']
            history.bind(state, items)
            state.setdefault('history_report_ids', []).append(history.report_id)
        if not preview:
            pending = [item for item in items if item['media_id'] in wanted
                       and item['media_id'] not in completed and item['lifecycle']['status'] == 'active']
            space = self.merge_space(root, items, pending, progress)
            state['disk_space'] = space
            if not space['ok']:
                details = ' / '.join(f"{v['path']}: 여유 {v['free_bytes'] / 1048576:.1f} MiB, 필요 {v['required_bytes'] / 1048576:.1f} MiB"
                                     for v in space['volumes'] if v['free_bytes'] < v['required_bytes'])
                return {'status': 'blocked_low_space', 'preview': False, 'operations': [],
                        'total': len(wanted), 'processed': len(operations), 'percent': 0,
                        'disk_space': space, 'warning': '공간 부족으로 병합을 시작하지 않았습니다. ' + details}
        def checkpoint(status='running'):
            state.update(status=status, processed=len(operations), total=len(wanted),
                         percent=round(len(operations) * 100 / len(wanted), 1) if wanted else 100,
                         inventory_complete=True, updated_at=now())
            if not preview:
                self.commit(items)
                atomic_json(session_path, state)
            progress({key: value for key, value in state.items() if key not in {'ids', 'operations'}})
        checkpoint()
        interrupted = False
        reserved, hashes = {}, {}
        for item in items:
            if item['media_id'] not in wanted or item['media_id'] in completed:
                continue
            if not preview and stopped():
                interrupted = True
                break
            if item['lifecycle']['status'] != 'active':
                operations.append({'media_id': item['media_id'], 'status': 'skipped'})
                continue
            c, date = item['classification'], item['capture']['date_key']
            target = self.merge_target(root, item)
            op = {'media_id': item['media_id'], 'destination': str(target), 'status': 'planned'}
            op['classification'] = {'category_id': c['category_id'], 'owner_id': c['owner_id']}
            op['date_key'] = date
            op['source_locations'] = [dict(loc) for loc in item['locations'] if loc['role'] == 'source']
            operations.append(op)
            source_location = item['locations'][0]
            state['source_file'] = source_location.get('path') or source_location.get('uri')
            def file_progress(path, role, action, emit=True):
                state.update(current_file=str(path), current_file_role=role, current_action=action,
                             target_file=str(path) if role == 'comparison_target' else str(target),
                             phase='planning' if preview else 'merging')
                if not emit:
                    return
                count = len(operations) - 1
                progress({**{key: value for key, value in state.items() if key not in {'ids', 'operations'}},
                          'processed': count, 'percent': round(count * 100 / len(wanted), 1) if wanted else 100})
            def comparing(path):
                file_progress(path, 'comparison_target', 'comparing_existing')
            try:
                original = target
                target = self.resolve_merge_target(root, item, reserved, hashes, on_compare=comparing)
                def record_target():
                    op.update(destination=str(target), original_destination=str(original), renamed=target != original)
                    if target != original:
                        op['rename_reason'] = 'name_collision'
                record_target()
                if preview:
                    file_progress(target, 'merge_destination', 'preview_target', emit=False)
                    if len(operations) % 100 == 0:
                        checkpoint()
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    op['status'] = 'reused'
                else:
                    temporary = target.with_name('.' + uid() + '.part')
                    try:
                        file_progress(state['source_file'], 'source', 'reading_source')
                        with self.materialize(item['locations'][0]) as source:
                            file_progress(target, 'merge_destination', 'copying')
                            shutil.copy2(source, temporary)
                        file_progress(temporary, 'temporary_copy', 'verifying_copy')
                        if digest(temporary) != item['sha256']:
                            raise ValueError('복사 검증 실패: 원본이 변경되었을 수 있습니다.')
                        while True:
                            try:
                                file_progress(target, 'merge_destination', 'publishing_copy')
                                self.publish_merge_copy(temporary, target)
                                op['status'] = 'copied'
                                break
                            except FileExistsError:
                                # A file appeared after planning; compare it and choose again.
                                hashes.clear()
                                target = self.resolve_merge_target(root, item, reserved, hashes, on_compare=comparing)
                                record_target()
                                if target.exists():
                                    op['status'] = 'reused'
                                    break
                    finally:
                        temporary.unlink(missing_ok=True)
                item['locations'] = [l for l in item['locations'] if not (l['role'] == 'managed' and l.get('path') == str(target))]
                item['locations'].append({'role': 'managed', 'protocol': 'file', 'path': str(target), 'uri': target.as_uri(), 'status': 'available', 'verified_at': now()})
            except Exception as exc:
                op.update(status='error', error=str(exc))
            # Keep the last completed target in checkpoints, including every
            # 25th file and the final job state; it is not an in-flight source.
            state.update(current_file=str(target), current_file_role='merge_destination',
                         current_action=op['status'], target_file=str(target))
            if len(operations) % 25 == 0:
                checkpoint()
            else:
                progress({'merge_id': state['merge_id'], 'total': len(wanted), 'processed': len(operations),
                          'percent': round(len(operations) * 100 / len(wanted), 1), 'current_file': str(target),
                          'current_file_role': state['current_file_role'], 'current_action': state['current_action'],
                          'source_file': state['source_file'], 'target_file': str(target), 'phase': 'merging'})
        checkpoint('stopped' if interrupted else 'completed')
        report = {'plan_id': uid(), 'preview': preview, 'operations': operations, 'created_at': now(),
                  'merge_id': state['merge_id'], 'status': state['status'],
                  'total': state['total'], 'processed': state['processed'], 'percent': state['percent']}
        report.update({key: state[key] for key in ('current_file', 'current_file_role', 'current_action', 'source_file', 'target_file') if key in state})
        if 'disk_space' in state:
            report['disk_space'] = state['disk_space']
        report['settings'] = {'boundary': str(self.boundary), 'db': str(self.db),
                              'managed_root': str(root), 'sources': self.config()['sources'],
                              'layout': 'managed_root/category_id/owner_id/year/month/name'}
        destinations = {}
        conflicts = set()
        by_id = {item['media_id']: item for item in items}
        for operation in operations:
            destination = operation.get('destination')
            if not destination:
                continue
            sha = by_id[operation['media_id']]['sha256']
            if destination in destinations and destinations[destination] != sha:
                conflicts.add(destination)
            destinations[destination] = sha
        report['destination_conflicts'] = sorted(conflicts)
        report['renamed_count'] = sum(bool(op.get('renamed')) for op in operations)
        report['warning'] = ('같은 출력 경로에 서로 다른 내용의 파일이 예정되어 있습니다. 분류나 파일명을 조정하세요.'
                             if conflicts else '동일 이름·동일 내용은 재사용하며, 내용이 다르면 _중복, _중복_2 등의 이름으로 보존합니다. 미리보기 이후 파일이 바뀌면 실행 경로도 달라질 수 있습니다.')
        atomic_json(self.db / 'plans' / (report['plan_id'] + '.json'), report)
        return report

    def trash(self, ids):
        with self.writing():
            items = self.items()
            selected = [i for i in items if i['media_id'] in ids and i['lifecycle']['status'] == 'active']
            if not selected:
                raise ValueError('삭제할 파일을 선택하세요.')
            root = self.local(self.config()['managed_root'])
            selected_ids = {i['media_id'] for i in selected}
            paths = {l['path'] for i in selected for l in i['locations'] if l['role'] == 'managed'}
            shared = {l['path'] for i in items if i['media_id'] not in selected_ids and i['lifecycle']['status'] == 'active' for l in i['locations'] if l['role'] == 'managed'}
            entry = {'trash_id': uid(), 'created_at': now(), 'status': 'moving', 'media_ids': sorted(selected_ids), 'moves': []}
            record = self.db / 'trash' / (entry['trash_id'] + '.json')
            for value in sorted(paths - shared):
                path = self.local(value)
                if not path.is_relative_to(root) or path.is_relative_to(root / '.trash'):
                    raise ValueError('관리 디렉토리 밖의 파일은 삭제할 수 없습니다.')
                if not path.exists():
                    continue
                target = root / '.trash' / entry['trash_id'] / path.relative_to(root)
                if not target.resolve().is_relative_to(root / '.trash'):
                    raise ValueError('휴지통 경계 밖입니다.')
                entry['moves'].append({'original': str(path), 'trash': str(target), 'sha256': digest(path), 'moved': False})
            atomic_json(record, entry)
            try:
                for move in entry['moves']:
                    path, target = Path(move['original']), Path(move['trash'])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(path, target)
                    move['moved'] = True
                    atomic_json(record, entry)
                for item in selected:
                    item['lifecycle'] = {'status': 'trashed', 'trash_entry_id': entry['trash_id']}
                self.commit(items)
                entry['status'] = 'trashed'
            except Exception:
                entry['status'] = 'recovery_required'
                atomic_json(record, entry)
                raise
            atomic_json(record, entry)
            return entry

    def trash_entries(self):
        return [read_json(p) for p in sorted((self.db / 'trash').glob('*.json'))]

    def restore(self, trash_id):
        with self.writing():
            record = self.db / 'trash' / (component(trash_id) + '.json')
            entry = read_json(record)
            if not entry or entry['status'] not in {'trashed', 'moving', 'recovery_required', 'restoring'}:
                raise ValueError('복원할 휴지통 항목이 없습니다.')
            root = self.local(self.config()['managed_root'])
            # A shared managed file may have been moved by a later trash operation.
            items = self.items()
            recorded = {m['original'] for m in entry['moves']}
            for item in items:
                if item['media_id'] not in entry['media_ids']:
                    continue
                for location in item['locations']:
                    if location['role'] != 'managed' or location['path'] in recorded or Path(location['path']).exists():
                        continue
                    found = next((m for other in self.trash_entries() for m in other['moves'] if m['original'] == location['path'] and Path(m['trash']).exists()), None)
                    if found:
                        entry['moves'].append(dict(found))
                        recorded.add(location['path'])
                    else:
                        raise ValueError('공유 복사본이 없습니다. 원본에서 다시 병합해야 합니다.')
            for move in entry['moves']:
                target, source = self.local(move['original']), self.local(move['trash'])
                if not target.is_relative_to(root) or target.is_relative_to(root / '.trash') or not source.is_relative_to(root / '.trash'):
                    raise ValueError('복원 경로가 관리 디렉토리 또는 휴지통 경계 밖입니다.')
                if target.exists() and source.exists():
                    raise ValueError('복원 경로에 파일이 존재합니다. 충돌을 해결하세요.')
                if not source.exists() and not target.exists():
                    raise ValueError('복원할 파일이 없습니다.')
                if digest(source if source.exists() else target) != move['sha256']:
                    raise ValueError('복원 파일 해시가 다릅니다.')
            entry['status'] = 'restoring'
            atomic_json(record, entry)
            for move in entry['moves']:
                target, source = self.local(move['original']), self.local(move['trash'])
                if source.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(source, target)
            for item in items:
                if item['media_id'] in entry['media_ids']:
                    item['lifecycle'] = {'status': 'active'}
            self.commit(items)
            entry['status'] = 'restored'
            atomic_json(record, entry)
            return entry

    def purge(self, trash_id):
        with self.writing():
            record = self.db / 'trash' / (component(trash_id) + '.json')
            entry = read_json(record)
            if not entry or entry['status'] not in {'trashed', 'purge_failed'}:
                raise ValueError('영구 삭제할 항목이 없습니다.')
            root = self.local(self.config()['managed_root']) / '.trash'
            entry['errors'] = []
            items = self.items()
            selected = set(entry['media_ids'])
            originals = {l['path'] for i in items if i['media_id'] in selected for l in i['locations'] if l['role'] == 'managed'}
            protected = {l['path'] for i in items if i['media_id'] not in selected and i['lifecycle']['status'] in {'active', 'trashed'} for l in i['locations'] if l['role'] == 'managed'}
            # Bytes shared by another recoverable trash entry must survive this purge.
            moves = {m['trash']: m for other in self.trash_entries() for m in other['moves'] if m['original'] in originals}
            entry['retained_shared_files'] = []
            for move in moves.values():
                try:
                    path = self.local(move['trash'])
                    if not path.is_relative_to(root):
                        raise ValueError('휴지통 경계 밖입니다.')
                    if move['original'] in protected:
                        if path.exists():
                            entry['retained_shared_files'].append(str(path))
                        continue
                    path.unlink(missing_ok=True)
                except OSError as exc:
                    entry['errors'].append(str(exc))
            entry['status'] = 'purge_failed' if entry['errors'] else 'purged'
            atomic_json(record, entry)
            if entry['status'] == 'purged':
                for item in items:
                    if item['media_id'] in entry['media_ids'] and item['lifecycle'].get('trash_entry_id') == trash_id:
                        item['lifecycle']['status'] = 'purged'
                self.commit(items)
            return entry

    def verify(self, ids, full=False):
        with self.writing():
            items = self.items()
            for item in items:
                if item['media_id'] not in ids or item['lifecycle']['status'] != 'active':
                    continue
                results = []
                for location in item['locations']:
                    try:
                        with self.materialize(location) as path:
                            matches = path.stat().st_size == item['size_bytes'] and (not full or digest(path) == item['sha256'])
                        results.append({'uri': location['uri'], 'status': 'ok' if matches else 'changed'})
                    except FileNotFoundError:
                        results.append({'uri': location['uri'], 'status': 'missing'})
                    except Exception as exc:
                        results.append({'uri': location['uri'], 'status': 'unreachable', 'error': str(exc)})
                item['verification'] = {'checked_at': now(), 'full': full, 'results': results}
            self.commit(items)
            return {'verified': len([i for i in items if i['media_id'] in ids])}
