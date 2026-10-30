"""Disk-backed ZIP downloads for explicitly selected active media."""
import hashlib
import re
import shutil
import tempfile
import time
import zipfile
from pathlib import Path

from library import EXTENSIONS, atomic_json, read_json, uid


def download_name(value):
    name = re.sub(r'[\x00-\x1f\x7f/\\<>:"|?*]', '_', value).strip(' .') or 'media'
    if Path(name).stem.upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
        name = 'file_' + name
    # Leave room for a duplicate suffix on common filesystems.
    suffix = Path(name).suffix
    while len(suffix.encode('utf-8')) > 40:
        suffix = suffix[:-1]
    stem = Path(name).stem
    while len((stem + suffix).encode('utf-8')) > 220:
        stem = stem[:-1]
    return stem + suffix


def media_location(item):
    return next((location for location in reversed(item['locations']) if location['role'] == 'managed' and location['status'] == 'available'), item['locations'][0])


class DownloadStore:
    ttl = 3600
    limit = 100

    def __init__(self, library):
        self.library = library
        self.directory = library.db / 'downloads'

    def cleanup(self):
        for path in self.directory.glob('*'):
            try:
                if (path.suffix == '.part' or (path.suffix == '.zip' and not path.with_suffix('.json').exists())) and re.fullmatch(r'[a-f0-9]{32}', path.stem) and path.stat().st_mtime + self.ttl <= time.time():
                    path.unlink(missing_ok=True)
            except OSError:
                continue
        for path in self.directory.glob('*.json'):
            try:
                token = path.stem
                if re.fullmatch(r'[a-f0-9]{32}', token) and read_json(path)['expires_at'] <= time.time():
                    (self.directory / (token + '.zip')).unlink(missing_ok=True)
                    path.unlink(missing_ok=True)
            except (OSError, ValueError, KeyError, TypeError):
                continue

    def selected_items(self, ids):
        if not isinstance(ids, list) or not 1 <= len(ids) <= self.limit or any(not isinstance(value, str) for value in ids):
            raise ValueError('다운로드할 파일은 1~100개 선택하세요.')
        values = []
        for media_id in dict.fromkeys(ids):
            item = self.library.item(media_id)
            if not item or item['lifecycle']['status'] != 'active':
                raise ValueError('선택한 미디어가 없거나 휴지통에 있습니다. 목록을 갱신하세요.')
            values.append(item)
        return values

    def prepare(self, ids, progress=None):
        return self._prepare(self.selected_items(ids), progress)

    def folder_items(self, paths):
        if not isinstance(paths, list) or not 1 <= len(paths) <= self.limit or any(not isinstance(p, str) or not p for p in paths):
            raise ValueError('다운로드할 파일은 1~100개 선택하세요.')
        items = []
        for value in dict.fromkeys(paths):
            path = self.library.local(value)
            if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
                raise ValueError('지원하는 미디어 파일이 아닙니다.')
            info = path.stat()
            items.append({'media_id': None, 'name': path.name, 'size_bytes': info.st_size,
                          'snapshot': (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns),
                          'locations': [{'role': 'source', 'status': 'available', 'protocol': 'file', 'path': str(path)}]})
        return items

    def prepare_folder(self, items, progress=None):
        """Prepare a snapshot produced by folder_items, without a library scan."""
        return self._prepare(items, progress)

    def _prepare(self, items, progress=None):
        progress = progress or (lambda state: None)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.cleanup()
        reserve = self.library.config().get('scan_min_free_mb', 512) * 1048576
        required = sum(item['size_bytes'] for item in items) + len(items) * 4096 + reserve
        if shutil.disk_usage(self.directory).free < required:
            raise ValueError('ZIP을 생성할 DB 디스크 여유 공간이 부족합니다.')
        token = uid()
        temporary = self.directory / (token + '.part')
        archive = self.directory / (token + '.zip')
        names, files = set(), []
        try:
            with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_STORED, allowZip64=True) as output:
                for index, item in enumerate(items):
                    # Recheck logical deletion before each file is added.
                    if item['media_id'] is not None:
                        current = self.library.item(item['media_id'])
                        if not current or current['lifecycle']['status'] != 'active':
                            raise ValueError('준비 중 선택한 파일이 삭제되었습니다. 다시 선택하세요.')
                    original = download_name(item['name'])
                    name, number = original, 1
                    while name.casefold() in names:
                        name = f"{Path(original).stem}_중복{'' if number == 1 else '_' + str(number)}{Path(original).suffix}"
                        number += 1
                    names.add(name.casefold())
                    progress({'phase': 'download', 'total': len(items), 'processed': index, 'percent': round(index * 100 / len(items), 1),
                              'inventory_complete': True, 'current_file': item['name'],
                              'current_file_role': 'archive_entry', 'current_action': 'archiving'})
                    location = media_location(item)
                    def transfer(total, downloaded):
                        needed = max(1048576, (total - downloaded) if total is not None else 8 * 1048576)
                        if shutil.disk_usage(tempfile.gettempdir()).free < reserve + needed:
                            raise ValueError('원격 파일 다운로드용 임시 디스크 공간이 부족합니다.')
                    with self.library.materialize(location, transfer=transfer) as path:
                        def check_snapshot():
                            info = path.stat()
                            if item.get('snapshot') and item['snapshot'] != (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns):
                                raise ValueError(f"파일이 변경되었습니다. 폴더를 다시 조회하세요: {item['name']}")
                        check_snapshot()
                        if path.stat().st_size != item['size_bytes']:
                            raise ValueError(f"파일 크기가 변경되었습니다. 재스캔하세요: {item['name']}")
                        hasher = hashlib.sha256()
                        with path.open('rb') as source, output.open(name, 'w', force_zip64=True) as target:
                            for block in iter(lambda: source.read(1024 * 1024), b''):
                                if shutil.disk_usage(self.directory).free < reserve + len(block):
                                    raise ValueError('ZIP 생성 중 디스크 여유 공간이 부족해 중단했습니다.')
                                target.write(block)
                                hasher.update(block)
                        check_snapshot()
                        if item.get('sha256') and hasher.hexdigest() != item['sha256']:
                            raise ValueError(f"파일 내용이 변경되었습니다. 재스캔하세요: {item['name']}")
                    files.append({'media_id': item['media_id'], 'original_name': item['name'], 'archive_name': name, 'size_bytes': item['size_bytes']})
            temporary.replace(archive)
            metadata = {'download_id': token, 'file_count': len(files), 'files': files, 'size_bytes': archive.stat().st_size,
                        'filename': 'BerePi_photos_' + time.strftime('%Y%m%d_%H%M%S', time.gmtime()) + '.zip', 'expires_at': time.time() + self.ttl}
            atomic_json(self.directory / (token + '.json'), metadata)
            progress({'phase': 'download', 'total': len(items), 'processed': len(items), 'percent': 100, 'inventory_complete': True})
            return metadata
        except BaseException:
            temporary.unlink(missing_ok=True)
            archive.unlink(missing_ok=True)
            (self.directory / (token + '.json')).unlink(missing_ok=True)
            raise

    def get(self, token):
        if not re.fullmatch(r'[a-f0-9]{32}', token):
            return None
        metadata = read_json(self.directory / (token + '.json'))
        if not metadata or metadata['expires_at'] <= time.time():
            self.cleanup()
            return None
        path = self.directory / (token + '.zip')
        if not path.is_file() or path.is_symlink():
            return None
        return path, metadata
