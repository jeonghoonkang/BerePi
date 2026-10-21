"""Verified directory bundles for library backup and relocation."""
import json
import os
import shutil
from pathlib import Path, PurePosixPath

from library import atomic_json, digest, now, read_json


def separate(first, second):
    return not (first.is_relative_to(second) or second.is_relative_to(first))


def inventory(root):
    if not root.is_dir() or root.is_symlink():
        raise ValueError(f'백업 디렉토리가 없습니다: {root}')
    result = {}
    def failed(exc):
        raise exc
    for base, dirs, files in os.walk(root, followlinks=False, onerror=failed):
        for name in dirs + files:
            path = Path(base) / name
            if path.is_symlink():
                raise ValueError(f'심볼릭 링크는 백업할 수 없습니다: {path}')
        for name in sorted(files):
            if name == '.write.lock':
                continue
            path = Path(base) / name
            if not path.is_file():
                raise ValueError(f'일반 파일이 아닙니다: {path}')
            stat = path.stat()
            result[path.relative_to(root).as_posix()] = (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    return result


def copy_verified(source, destination, expected=None):
    destination.parent.mkdir(parents=True, exist_ok=True)
    before = source.stat()
    sha = digest(source)
    shutil.copy2(source, destination)
    after = source.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError(f'복사 중 파일이 변경됐습니다: {source}')
    if destination.stat().st_size != before.st_size or digest(destination) != sha:
        raise ValueError(f'복사 검증 실패: {source}')
    if expected and (before.st_size != expected['size_bytes'] or sha != expected['sha256']):
        raise ValueError(f'백업 파일 무결성 오류: {source}')
    return {'size_bytes': before.st_size, 'sha256': sha, 'mtime_ns': before.st_mtime_ns}


def create_backup(library, destination):
    destination = Path(destination).expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError('백업 대상은 존재하지 않는 새 디렉토리여야 합니다.')
    destination = destination.resolve()
    with library.writing():
        managed = library.local(library.config()['managed_root'])
        if not separate(library.db, managed) or not all(separate(destination, root) for root in (library.db, managed)):
            raise ValueError('DB·관리 디렉토리·백업 경로는 서로 분리되어야 합니다.')
        roots = {'db': library.db, 'managed': managed}
        snapshots = {section: inventory(root) for section, root in roots.items()}
        total = sum(info[0] for files in snapshots.values() for info in files.values())
        destination.parent.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(destination.parent).free < total + 16 * 1024 * 1024:
            raise ValueError('백업 디스크 공간이 부족합니다.')
        destination.mkdir()
        try:
            records = []
            for section, root in roots.items():
                (destination / section).mkdir()
                for relative in sorted(snapshots[section]):
                    value = copy_verified(root / relative, destination / section / relative)
                    records.append({'path': section + '/' + relative, **value})
            if any(inventory(root) != snapshots[section] for section, root in roots.items()):
                raise ValueError('백업 중 파일 목록 또는 내용이 변경됐습니다. 변경 작업을 멈추고 다시 실행하세요.')
            copied = {r['path']: r for r in records}
            without_copy = []
            for item in library.items():
                if item['lifecycle']['status'] != 'active':
                    continue
                available = False
                for location in item['locations']:
                    if location['role'] != 'managed' or location.get('status') != 'available':
                        continue
                    path = library.local(location['path'])
                    if not path.is_relative_to(managed):
                        raise ValueError('등록된 관리 복사본이 관리 디렉토리 밖에 있습니다.')
                    record = copied.get('managed/' + path.relative_to(managed).as_posix())
                    if not record or record['sha256'] != item['sha256'] or record['size_bytes'] != item['size_bytes']:
                        raise ValueError(f'등록된 관리 복사본이 없거나 손상됐습니다: {path}')
                    available = True
                if not available:
                    without_copy.append(item['media_id'])
            manifest = {'format': 'photo-browser-backup', 'version': 1, 'status': 'complete', 'created_at': now(),
                        'original_db': str(library.db), 'original_managed_root': str(managed),
                        'original_db_uri': library.db.as_uri(), 'original_managed_uri': managed.as_uri(),
                        'file_count': len(records), 'total_bytes': total, 'files': records,
                        'includes_original_sources': False, 'active_items_without_managed_copy': len(without_copy)}
            atomic_json(destination / 'manifest.json', manifest)
        except BaseException:
            shutil.rmtree(destination)
            raise
    return {'status': 'completed', 'backup': str(destination), 'file_count': len(records), 'total_bytes': total,
            'active_items_without_managed_copy': len(without_copy),
            'warning': '원본 소스는 포함하지 않습니다. 관리 복사본이 없는 활성 항목은 사진 바이트가 백업되지 않습니다.'}


def load_manifest(bundle):
    manifest = read_json(bundle / 'manifest.json')
    if not isinstance(manifest, dict) or manifest.get('format') != 'photo-browser-backup' or manifest.get('version') != 1 or manifest.get('status') != 'complete':
        raise ValueError('완료된 Photo Browser 백업이 아닙니다.')
    if not isinstance(manifest.get('files'), list):
        raise ValueError('백업 파일 목록이 올바르지 않습니다.')
    seen = set()
    for entry in manifest['files']:
        path = entry['path']
        if not isinstance(path, str):
            raise ValueError('백업 파일 경로가 문자열이 아닙니다.')
        relative = PurePosixPath(path)
        if ('\\' in path or ':' in path or relative.is_absolute()
                or '..' in relative.parts or len(relative.parts) < 2 or relative.parts[0] not in {'db', 'managed'}
                or relative.as_posix() != path or path in seen):
            raise ValueError('백업에 유효하지 않거나 중복된 경로가 있습니다.')
        seen.add(path)
    if 'db/config.json' not in seen:
        raise ValueError('백업에 설정 파일이 없습니다.')
    actual = {section + '/' + path for section in ('db', 'managed') for path in inventory(bundle / section)}
    if actual != seen:
        raise ValueError('백업 파일 목록이 실제 파일과 다릅니다.')
    if len(seen) != manifest['file_count'] or sum(e['size_bytes'] for e in manifest['files']) != manifest['total_bytes']:
        raise ValueError('백업 집계 정보가 올바르지 않습니다.')
    return manifest


def verify_backup(bundle):
    bundle = Path(bundle).expanduser().resolve()
    manifest = load_manifest(bundle)
    for entry in manifest['files']:
        path = bundle / entry['path']
        if path.stat().st_size != entry['size_bytes'] or digest(path) != entry['sha256']:
            raise ValueError(f'백업 파일 무결성 오류: {path}')
    return {'status': 'verified', 'backup': str(bundle),
            'file_count': manifest['file_count'], 'total_bytes': manifest['total_bytes']}


def relocate(value, mappings):
    if isinstance(value, dict):
        # User-entered classification and capture metadata are not file references.
        return {key: child if key in {'classification', 'capture'} else relocate(child, mappings)
                for key, child in value.items()}
    if isinstance(value, list):
        return [relocate(child, mappings) for child in value]
    if isinstance(value, str):
        for old, new in mappings:
            if value == old:
                return new
            if value.startswith(old + '/') or value.startswith(old + '\\'):
                suffix = value[len(old):].replace('\\', '/')
                return new + suffix
    return value


def restore_backup(bundle, destination):
    bundle = Path(bundle).expanduser().resolve()
    target = Path(destination).expanduser().absolute()
    if target.exists() or target.is_symlink():
        raise ValueError('복원 대상은 존재하지 않는 새 디렉토리여야 합니다.')
    target = target.resolve()
    if not separate(bundle, target):
        raise ValueError('백업과 복원 경로는 분리되어야 합니다.')
    manifest = load_manifest(bundle)
    target.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(target.parent).free < manifest['total_bytes'] + 16 * 1024 * 1024:
        raise ValueError('복원 디스크 공간이 부족합니다.')
    target.mkdir()
    try:
        for section in ('db', 'managed'):
            (target / section).mkdir()
        for entry in manifest['files']:
            copy_verified(bundle / entry['path'], target / entry['path'], entry)
        mappings = [(manifest['original_managed_root'], str(target / 'managed')),
                    (manifest['original_db'], str(target / 'db')),
                    (manifest['original_managed_uri'], (target / 'managed').as_uri()),
                    (manifest['original_db_uri'], (target / 'db').as_uri())]
        # Historical HTML reports remain verbatim; structured operational records are relocated.
        for path in (target / 'db').rglob('*'):
            if path.suffix not in {'.json', '.jsonl'} or not path.is_file():
                continue
            if path.suffix == '.json':
                original = read_json(path)
                value = relocate(original, mappings)
                if value != original:
                    atomic_json(path, value)
            else:
                # A torn last journal record is recoverable by ScanEngine on resume.
                lines = path.read_bytes().splitlines(keepends=True)
                updated = []
                for index, line in enumerate(lines):
                    try:
                        value = json.loads(line)
                    except (ValueError, UnicodeDecodeError):
                        if index != len(lines) - 1 or line.endswith(b'\n'):
                            raise
                        updated.append(line)
                        continue
                    if index == len(lines) - 1 and not line.endswith(b'\n'):
                        updated.append(line)
                    else:
                        updated.append((json.dumps(relocate(value, mappings), ensure_ascii=False) + '\n').encode('utf-8'))
                path.write_bytes(b''.join(updated))
        config_path = target / 'db' / 'config.json'
        config = read_json(config_path)
        config['managed_root'] = str(target / 'managed')
        atomic_json(config_path, config)
        record = {'status': 'completed', 'restored_at': now(), 'backup': str(bundle),
                  'db': str(target / 'db'), 'managed_root': str(target / 'managed'), 'root': str(target),
                  'file_count': manifest['file_count'], 'total_bytes': manifest['total_bytes'],
                  'active_items_without_managed_copy': manifest.get('active_items_without_managed_copy', 0),
                  'warning': '원본 소스는 포함하지 않습니다. 원본 경로·원격 인증은 별도로 재연결하세요. 과거 HTML 보고서는 원래 경로를 유지합니다.'}
        atomic_json(target / 'restore.json', record)
    except BaseException:
        shutil.rmtree(target)
        raise
    return record
