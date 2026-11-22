"""Cached folder accounting and live filesystem capacity, without hashing media."""
import copy
from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import stat
import sys
import threading
import time

from library import atomic_json, read_json


LABELS = {'db': '라이브러리 DB', 'sources': '원본 소스', 'managed': '관리 라이브러리 (휴지통 포함)'}


def human_bytes(value):
    if value is None: return '미집계'
    size = float(value)
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB'):
        if abs(size) < 1024 or unit == 'PiB': return f'{size:,.2f} {unit}'
        size /= 1024


class StorageUsage:
    def __init__(self, db, boundary='/', ttl=30, persist=True):
        self.db = Path(db).expanduser().resolve()
        self.boundary = Path(boundary).expanduser().resolve()
        self.ttl = ttl
        self.persist = persist
        self.lock = threading.Lock()
        self.worker = None
        self.checked = None
        self.announce = None
        self.stop = threading.Event()
        self.value = {'state': 'pending', 'categories': {}, 'volumes': [], 'checked_at': None, 'errors': []}
        try:
            cached = read_json(self.db / 'storage-usage' / 'cache.json', {})
            if cached.get('format') == 'photo-browser-storage-usage': self.value = cached
        except (OSError, ValueError, TypeError):
            pass

    def layout(self):
        config = read_json(self.db / 'config.json', {})
        roots = [{'kind': 'db', 'label': 'DB', 'path': str(self.db)}]
        if config.get('managed_root'):
            roots.append({'kind': 'managed', 'label': '관리 라이브러리', 'path': config['managed_root']})
        for source in config.get('sources', []):
            roots.append({'kind': 'sources', 'label': '원본 ' + source['source_id'], 'path': source['root'],
                          'remote': source.get('protocol', 'file') != 'file'})
        return roots

    def local(self, root):
        if root.get('remote'): raise ValueError('원격 HTTP/WebDAV 저장소의 실제 용량은 서버에서 측정할 수 없습니다.')
        raw = Path(root['path']).expanduser()
        path = raw.resolve()
        if raw.is_symlink() or not path.is_relative_to(self.boundary):
            raise ValueError('링크 또는 허용 범위 밖의 저장소입니다.')
        return path

    def disks(self, roots=None):
        volumes, errors = {}, []
        for root in roots or self.layout():
            try:
                path = self.local(root)
                # Future DB/library targets use their nearest existing parent.
                # Missing originals never inherit a misleading parent capacity.
                if root['kind'] != 'sources':
                    while not path.exists() and path != path.parent: path = path.parent
                info = path.stat()
                if not stat.S_ISDIR(info.st_mode): raise ValueError('디렉토리가 아닙니다.')
                key = str(info.st_dev) if info.st_dev else str(info.st_dev) + ':' + path.anchor
                if key not in volumes:
                    usage = shutil.disk_usage(path)
                    volumes[key] = {'device_id': key, 'path': str(path), 'total_bytes': usage.total,
                                    'used_bytes': usage.used, 'free_bytes': usage.free,
                                    'used_percent': round(usage.used * 100 / usage.total, 1) if usage.total else None,
                                    'labels': [], 'roles': []}
                for name, value in [('labels', root['label']), ('roles', root['kind'])]:
                    if value not in volumes[key][name]: volumes[key][name].append(value)
            except (OSError, ValueError) as exc:
                errors.append({'label': root['label'], 'path': root['path'], 'error': str(exc)})
        return list(volumes.values()), errors

    def snapshot(self, force=False):
        roots = self.layout()
        with self.lock:
            if self.value.get('roots') != roots:
                self.value = {'state': 'pending', 'categories': {}, 'volumes': [], 'checked_at': None, 'errors': [], 'roots': roots}
                self.checked = None
            running = self.worker is not None and self.worker.is_alive()
            if not running and (force or self.checked is None or time.monotonic() - self.checked >= self.ttl):
                self.worker = threading.Thread(target=self.refresh, name='photo-storage-usage', daemon=True)
                self.worker.start(); running = True
            return {**copy.deepcopy(self.value), 'running': running, 'refresh_seconds': self.ttl}

    def current(self):
        roots = self.layout()
        with self.lock:
            value = copy.deepcopy(self.value) if self.value.get('roots') == roots else {
                'state': 'pending', 'roots': roots, 'categories': {}, 'checked_at': None}
        volumes, errors = self.disks(roots)
        # Keep any measured nested filesystems, updating their capacity too.
        extras = [{'kind': volume['roles'][0], 'label': ' / '.join(volume['labels']), 'path': volume['path']}
                  for volume in value.get('volumes', []) if not any(v['device_id'] == volume['device_id'] for v in volumes)]
        if extras: volumes, errors = self.disks(roots + extras)
        return {**value, 'state': 'partial' if errors and value.get('state') == 'ready' else value.get('state', 'pending'),
                'volumes': volumes, 'errors': errors,
                'capacity_checked_at': datetime.now(timezone.utc).isoformat()}

    def refresh(self):
        try:
            self.measure()
        except Exception as exc:
            with self.lock:
                self.value = {**self.value, 'state': 'error', 'errors': [{'error': str(exc)}]}
                self.checked = time.monotonic()

    @contextmanager
    def running(self):
        try:
            yield
        finally:
            self.stop.set()
            if self.worker: self.worker.join(timeout=1)

    def measure(self):
        if self.stop.is_set(): return
        roots = self.layout()
        volumes, disk_errors = self.disks(roots)
        categories = {kind: {'label': label, 'state': 'pending', 'logical_bytes': None, 'allocated_bytes': None,
                            'file_count': 0, 'unique_file_count': 0, 'skipped': 0, 'errors': [], 'allocation_estimated': False}
                      for kind, label in LABELS.items()}
        with self.lock:
            if self.value.get('roots') == roots:
                self.value.update(volumes=volumes, errors=disk_errors)
        exclusions = [Path(root['path']).resolve() for root in roots if root['kind'] in {'db', 'managed'}]
        discovered = []
        devices = {volume['device_id'] for volume in volumes}
        for kind, category in categories.items():
            targets, seen, measured = [], set(), 0
            for root in (root for root in roots if root['kind'] == kind):
                try:
                    path = self.local(root)
                    if not path.is_dir(): raise ValueError('디렉토리가 없거나 연결되지 않았습니다.')
                    if kind == 'sources' and any(path.is_relative_to(excluded) for excluded in exclusions):
                        raise ValueError('DB·관리 폴더와 겹치는 원본 경로는 제외합니다.')
                    if not any(path.is_relative_to(target) for target in targets): targets.append(path)
                except (OSError, ValueError) as exc:
                    category['skipped'] += 1
                    if len(category['errors']) < 5: category['errors'].append(root['label'] + ': ' + str(exc))
            # Parent roots cover child roots without repeated traversal.
            targets = [path for path in targets if not any(path != other and path.is_relative_to(other) for other in targets)]
            logical = allocated = 0
            for target in targets:
                folders = [target]
                while folders:
                    if self.stop.is_set(): return
                    folder = folders.pop()
                    try:
                        with os.scandir(folder) as entries:
                            measured += 1
                            for entry in entries:
                                if self.stop.is_set(): return
                                try:
                                    info = entry.stat(follow_symlinks=False)
                                    if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                                        category['skipped'] += 1
                                        continue
                                    path = Path(entry.path)
                                    if kind == 'sources' and any(path.is_relative_to(excluded) for excluded in exclusions): continue
                                    device = str(info.st_dev) if info.st_dev else str(info.st_dev) + ':' + path.anchor
                                    if device not in devices and (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                                        devices.add(device)
                                        discovered.append({'kind': kind, 'label': LABELS[kind] + ' 하위 저장소',
                                                           'path': str(path if stat.S_ISDIR(info.st_mode) else path.parent)})
                                    if stat.S_ISDIR(info.st_mode): folders.append(path)
                                    elif stat.S_ISREG(info.st_mode):
                                        category['file_count'] += 1
                                        identity = (info.st_dev, info.st_ino) if info.st_ino else str(path)
                                        if identity in seen: continue
                                        seen.add(identity)
                                        logical += info.st_size
                                        blocks = getattr(info, 'st_blocks', None)
                                        allocated += blocks * 512 if blocks is not None else info.st_size
                                        category['allocation_estimated'] |= blocks is None
                                except OSError as exc:
                                    category['skipped'] += 1
                                    if len(category['errors']) < 5: category['errors'].append(str(exc))
                    except OSError as exc:
                        category['skipped'] += 1
                        if len(category['errors']) < 5: category['errors'].append(str(exc))
            if measured or (not targets and not category['skipped']):
                category.update(logical_bytes=logical, allocated_bytes=allocated, unique_file_count=len(seen),
                                state='partial' if category['skipped'] else 'ready')
            else: category['state'] = 'error'
        # Capacity is refreshed after a potentially lengthy directory walk.
        volumes, disk_errors = self.disks(roots + discovered)
        value = {'format': 'photo-browser-storage-usage', 'roots': roots, 'categories': categories,
                 'volumes': volumes, 'errors': disk_errors,
                 'state': 'partial' if disk_errors or any(c['state'] != 'ready' for c in categories.values()) else 'ready',
                 'checked_at': datetime.now(timezone.utc).isoformat()}
        if self.stop.is_set(): return
        if roots != self.layout(): return self.current()
        with self.lock:
            self.value = value; self.checked = time.monotonic()
        if self.persist:
            try:
                from source_health import audit_lock
                with audit_lock(self.db): atomic_json(self.db / 'storage-usage' / 'cache.json', value)
            except (OSError, ValueError):
                pass  # Capacity remains available even if a backup owns the cache lock.
        if self.announce is not None:
            try:
                print('폴더 용량 집계 완료: ' + ' · '.join('{} {}'.format(LABELS[kind], human_bytes(category['logical_bytes']))
                      for kind, category in categories.items()) + ' · ' + value['checked_at'], file=self.announce, flush=True)
            except (OSError, ValueError): pass
        return value

    def startup(self, stream=None, background=False):
        stream = stream if stream is not None else sys.stderr
        cached = self.current()
        volumes, errors = cached['volumes'], cached['errors']
        print('\n저장 공간 현황 (파일시스템별, 동일 파일시스템 중복 제외)', file=stream, flush=True)
        for kind, label in LABELS.items():
            category = cached.get('categories', {}).get(kind, {})
            print(f"  {label}: 파일 {human_bytes(category.get('logical_bytes'))} · 할당 {human_bytes(category.get('allocated_bytes'))}"
                  + (' · 일부만 집계' if category.get('state') == 'partial' else ''), file=stream, flush=True)
        for volume in volumes:
            print('  {}: 전체 {} · 사용 {} · 사용 가능 {} · 사용률 {}%'.format(' / '.join(volume['labels']),
                human_bytes(volume['total_bytes']), human_bytes(volume['used_bytes']), human_bytes(volume['free_bytes']),
                volume['used_percent']), file=stream, flush=True)
        for error in errors:
            print('  {}: 용량 확인 불가 · {}'.format(error['label'], error['error']), file=stream, flush=True)
        print('  폴더 최근 집계: {} · 최초/새 집계: cli.py storage-usage --refresh'.format(cached.get('checked_at') or '미집계'), file=stream, flush=True)
        if background:
            self.announce = stream
            self.snapshot()
