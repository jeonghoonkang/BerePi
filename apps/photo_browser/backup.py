"""Verified directory/ZIP bundles for library backup and relocation."""
import hashlib
import json
import os
import re
import shutil
import stat
import zipfile
import zlib
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

from library import atomic_json, digest, now, read_json, write_library_locations


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


def create_backup(library, destination, archive_format=None):
    archive_format = archive_format or ('zip' if Path(destination).suffix.lower() == '.zip' else 'directory')
    if archive_format == 'zip':
        return create_zip_backup(library, destination)
    if archive_format != 'directory':
        raise ValueError('백업 형식은 directory 또는 zip이어야 합니다.')
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
            manifest = make_manifest(library, managed, records, total)
            atomic_json(destination / 'manifest.json', manifest)
        except BaseException:
            shutil.rmtree(destination)
            raise
    return {'status': 'completed', 'backup': str(destination), 'file_count': len(records), 'total_bytes': total,
            'active_items_without_managed_copy': manifest['active_items_without_managed_copy'],
            'warning': '원본 소스는 포함하지 않습니다. 관리 복사본이 없는 활성 항목은 사진 바이트가 백업되지 않습니다.'}


def make_manifest(library, managed, records, total):
    copied = {r['path']: r for r in records}
    without_copy = 0
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
            without_copy += 1
    return {'format': 'photo-browser-backup', 'version': 1, 'status': 'complete', 'created_at': now(),
            'original_db': str(library.db), 'original_managed_root': str(managed),
            'original_db_uri': library.db.as_uri(), 'original_managed_uri': managed.as_uri(),
            'original_allowed_root': str(library.boundary),
            'source_roots': [{k: source.get(k) for k in ('source_id', 'protocol', 'root')} for source in library.config()['sources']],
            'file_count': len(records), 'total_bytes': total, 'files': records,
            'includes_original_sources': False, 'active_items_without_managed_copy': without_copy}


def validate_manifest(manifest):
    if not isinstance(manifest, dict) or manifest.get('format') != 'photo-browser-backup' or manifest.get('version') != 1 or manifest.get('status') != 'complete':
        raise ValueError('완료된 Photo Browser 백업이 아닙니다.')
    if not isinstance(manifest.get('files'), list):
        raise ValueError('백업 파일 목록이 올바르지 않습니다.')
    for key in ('original_db', 'original_managed_root', 'original_db_uri', 'original_managed_uri'):
        if not isinstance(manifest.get(key), str) or not manifest[key]:
            raise ValueError('백업의 원래 경로 정보가 올바르지 않습니다.')
    if any(type(manifest.get(key)) is not int or manifest[key] < 0 for key in ('file_count', 'total_bytes')):
        raise ValueError('백업 집계 정보가 올바르지 않습니다.')
    seen = set()
    for entry in manifest['files']:
        if (not isinstance(entry, dict) or type(entry.get('size_bytes')) is not int or entry['size_bytes'] < 0
                or type(entry.get('mtime_ns')) is not int or not isinstance(entry.get('sha256'), str)
                or not re.fullmatch(r'[a-f0-9]{64}', entry['sha256'])):
            raise ValueError('백업 파일 검증 정보가 올바르지 않습니다.')
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
    if len(seen) != manifest['file_count'] or sum(e['size_bytes'] for e in manifest['files']) != manifest['total_bytes']:
        raise ValueError('백업 집계 정보가 올바르지 않습니다.')
    return manifest


def load_manifest(bundle):
    manifest = validate_manifest(read_json(bundle / 'manifest.json'))
    actual = {section + '/' + path for section in ('db', 'managed') for path in inventory(bundle / section)}
    if actual != {entry['path'] for entry in manifest['files']}:
        raise ValueError('백업 파일 목록이 실제 파일과 다릅니다.')
    return manifest


def create_zip_backup(library, destination):
    destination = Path(destination).expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError('백업 대상은 존재하지 않는 새 ZIP 파일이어야 합니다.')
    destination = destination.resolve()
    with library.writing():
        managed = library.local(library.config()['managed_root'])
        if not separate(library.db, managed) or not all(separate(destination, root) for root in (library.db, managed)):
            raise ValueError('DB·관리 디렉토리·백업 경로는 서로 분리되어야 합니다.')
        roots = {'db': library.db, 'managed': managed}
        snapshots = {section: inventory(root) for section, root in roots.items()}
        total = sum(info[0] for files in snapshots.values() for info in files.values())
        overhead = 16 * 1048576 + sum(len(files) for files in snapshots.values()) * 4096 + total // 1000
        destination.parent.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(destination.parent).free < total + overhead:
            raise ValueError('백업 디스크 공간이 부족합니다.')
        owned = False
        try:
            # Exclusive creation also protects against concurrent backup commands.
            with destination.open('xb') as stream:
                owned = True
                with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
                    archive.writestr('db/', b'')
                    archive.writestr('managed/', b'')
                    records = []
                    for section, root in roots.items():
                        for relative in sorted(snapshots[section]):
                            path, name = root / relative, section + '/' + relative
                            before = path.stat()
                            hasher, size = hashlib.sha256(), 0
                            info = zipfile.ZipInfo(name)
                            info.compress_type = zipfile.ZIP_DEFLATED
                            with path.open('rb') as source, archive.open(info, 'w', force_zip64=True) as output:
                                for block in iter(lambda: source.read(1048576), b''):
                                    if shutil.disk_usage(destination.parent).free < 16 * 1048576 + len(block):
                                        raise ValueError('ZIP 백업 중 디스크 공간이 부족합니다.')
                                    output.write(block)
                                    size += len(block)
                                    hasher.update(block)
                            after = path.stat()
                            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns) or size != before.st_size:
                                raise ValueError(f'복사 중 파일이 변경됐습니다: {path}')
                            records.append({'path': name, 'size_bytes': size, 'sha256': hasher.hexdigest(), 'mtime_ns': before.st_mtime_ns})
                    if any(inventory(root) != snapshots[section] for section, root in roots.items()):
                        raise ValueError('백업 중 파일 목록 또는 내용이 변경됐습니다. 변경 작업을 멈추고 다시 실행하세요.')
                    manifest = make_manifest(library, managed, records, total)
                    manifest['container'] = 'zip'
                    archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8'))
                stream.flush()
                os.fsync(stream.fileno())
            verify_backup(destination)
        except BaseException:
            if owned:
                destination.unlink(missing_ok=True)
            raise
    return {'status': 'completed', 'backup': str(destination), 'container': 'zip',
            'file_count': len(records), 'total_bytes': total, 'archive_bytes': destination.stat().st_size,
            'active_items_without_managed_copy': manifest['active_items_without_managed_copy'],
            'warning': '원본 소스는 포함하지 않습니다. 관리 복사본이 없는 활성 항목은 사진 바이트가 백업되지 않습니다.'}


@contextmanager
def open_bundle(bundle):
    """Expose directory and ZIP payloads without extracting an untrusted archive."""
    if bundle.is_dir():
        yield load_manifest(bundle), None
        return
    try:
        with zipfile.ZipFile(bundle) as archive:
            entries = archive.infolist()
            names = [info.filename for info in entries]
            if len(set(names)) != len(names):
                raise ValueError('ZIP에 중복된 파일 경로가 있습니다.')
            for info in entries:
                kind = stat.S_IFMT(info.external_attr >> 16)
                if kind not in {0, stat.S_IFREG, stat.S_IFDIR} or info.flag_bits & 1:
                    raise ValueError('ZIP에 지원하지 않는 링크·특수 파일·암호화 항목이 있습니다.')
            info = archive.getinfo('manifest.json')
            if info.file_size > 64 * 1048576:
                raise ValueError('백업 manifest.json 크기 한도를 초과했습니다.')
            manifest = validate_manifest(json.loads(archive.read(info)))
            expected = {'manifest.json', 'db/', 'managed/'} | {entry['path'] for entry in manifest['files']}
            if set(names) != expected:
                raise ValueError('백업 파일 목록이 ZIP 파일 목록과 다릅니다.')
            for entry in manifest['files']:
                if archive.getinfo(entry['path']).file_size != entry['size_bytes']:
                    raise ValueError('백업 파일 크기 정보가 ZIP과 다릅니다.')
            yield manifest, archive
    except (zipfile.BadZipFile, zlib.error, RuntimeError, NotImplementedError, EOFError) as exc:
        raise ValueError(f'백업 ZIP이 손상되었거나 지원하지 않는 형식입니다: {exc}') from exc


def read_zip_file(archive, entry, destination=None):
    hasher, size = hashlib.sha256(), 0
    with archive.open(entry['path']) as source:
        for block in iter(lambda: source.read(1048576), b''):
            size += len(block)
            if size > entry['size_bytes']:
                raise ValueError('백업 파일 크기 한도를 초과했습니다.')
            hasher.update(block)
            if destination is not None:
                destination.write(block)
    if size != entry['size_bytes'] or hasher.hexdigest() != entry['sha256']:
        raise ValueError(f"백업 파일 무결성 오류: {entry['path']}")


def verify_backup(bundle):
    bundle = Path(bundle).expanduser().resolve()
    with open_bundle(bundle) as (manifest, archive):
        for entry in manifest['files']:
            if archive is not None:
                read_zip_file(archive, entry)
            else:
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
    with open_bundle(bundle) as (manifest, archive):
        return restore_payload(bundle, target, manifest, archive)


def restore_payload(bundle, target, manifest, archive):
    target.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(target.parent).free < manifest['total_bytes'] + 16 * 1024 * 1024:
        raise ValueError('복원 디스크 공간이 부족합니다.')
    target.mkdir()
    try:
        for section in ('db', 'managed'):
            (target / section).mkdir()
        for entry in manifest['files']:
            if archive is None:
                copy_verified(bundle / entry['path'], target / entry['path'], entry)
            else:
                path = target / entry['path']
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('xb') as output:
                    read_zip_file(archive, entry, output)
                os.utime(path, ns=(entry['mtime_ns'], entry['mtime_ns']))
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
        write_library_locations(target / 'db', target / 'managed', config=config, new_pair=True)
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
