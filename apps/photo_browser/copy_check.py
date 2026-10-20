"""Read-only comparison of current source files and registered managed copies."""
import os
from pathlib import Path

from library import EXTENSIONS, digest, now


def local_inventory(library, root, recursive=True, excluded=()):
    root = library.local(root)
    if not root.is_dir():
        raise ValueError(f'디렉토리가 없습니다: {root}')
    def failed(exc):
        raise exc
    for base, directories, files in os.walk(root, onerror=failed, followlinks=False):
        directories[:] = sorted(d for d in directories if d != '.trash' and not (Path(base) / d).is_symlink()
                                and not any((Path(base) / d).resolve().is_relative_to(p) for p in excluded))
        for name in sorted(files):
            path = Path(base) / name
            if name.startswith('._') or path.suffix.lower() not in EXTENSIONS or path.is_symlink():
                continue
            path = library.local(path)
            if not any(path.is_relative_to(p) for p in excluded):
                yield path
        if not recursive:
            directories.clear()


def compare_copies(library, source_id=None, quick=False):
    # Prevent concurrent server/CLI writes for a consistent DB and copy snapshot.
    with library.writing():
        config = library.config()
        sources = [s for s in config['sources'] if source_id is None or s['source_id'] == source_id]
        if not sources:
            raise ValueError('등록된 소스를 찾지 못했습니다.')
        managed = library.local(config['managed_root'])
        items = library.items()
        issues, summaries, destinations = [], [], {}
        checked = 0

        def inspect(path):
            return {'size_bytes': path.stat().st_size, 'sha256': None if quick else digest(path)}

        for source in sources:
            sid = source['source_id']
            actual = {}
            try:
                if source.get('protocol', 'file') == 'file':
                    root = library.local(source['root'])
                    if root.is_relative_to(managed) or root.is_relative_to(library.db):
                        raise ValueError('관리 디렉토리 또는 DB는 원본으로 비교할 수 없습니다.')
                    entries = ((p.as_uri(), {'path': str(p)}) for p in local_inventory(
                        library, root, source.get('recursive', True), (managed, library.db)))
                else:
                    entries = library.remote_files(source)
                for uri, info in entries:
                    try:
                        location = {**info, 'uri': uri, 'source_id': sid, 'protocol': source.get('protocol', 'file')}
                        with library.materialize(location) as path:
                            actual[uri] = inspect(path)
                    except Exception as exc:
                        issues.append({'source_id': sid, 'uri': uri, 'status': 'source_unreadable', 'error': str(exc)})
            except Exception as exc:
                issues.append({'source_id': sid, 'status': 'inventory_failed', 'error': str(exc)})
            known = {}
            for item in items:
                for loc in item['locations']:
                    if loc['role'] == 'source' and loc.get('source_id') == sid:
                        known[loc['uri']] = item
            active = {uri: item for uri, item in known.items() if item['lifecycle']['status'] == 'active'}
            summaries.append({'source_id': sid, 'root': source['root'], 'file_count': len(actual),
                              'total_bytes': sum(v['size_bytes'] for v in actual.values()),
                              'indexed_active_count': len(active),
                              'indexed_active_bytes': sum(i['size_bytes'] for i in active.values()),
                              'excluded_inactive_count': sum(uri in actual for uri in known if uri not in active)})
            for uri in actual.keys() - known.keys():
                issues.append({'source_id': sid, 'uri': uri, 'status': 'not_scanned'})
            for uri, item in active.items():
                detail = {'source_id': sid, 'uri': uri, 'media_id': item['media_id']}
                original = actual.get(uri)
                source_matches = original is not None and original['size_bytes'] == item['size_bytes'] and (quick or original['sha256'] == item['sha256'])
                if original is None:
                    issues.append({**detail, 'status': 'source_missing_or_unreadable'})
                elif not source_matches:
                    issues.append({**detail, 'status': 'source_changed'})
                copies = [loc for loc in item['locations'] if loc['role'] == 'managed' and loc.get('status') == 'available']
                if not copies:
                    issues.append({**detail, 'status': 'copy_not_registered'})
                    continue
                valid = False
                for loc in copies:
                    try:
                        path = library.local(loc['path'])
                        if not path.is_relative_to(managed) or path.is_relative_to(managed / '.trash'):
                            raise ValueError('관리 디렉토리 밖의 복사본입니다.')
                        if path not in destinations:
                            destinations[path] = inspect(path)
                        value = destinations[path]
                        matches = value['size_bytes'] == item['size_bytes'] and (quick or value['sha256'] == item['sha256'])
                        if matches:
                            valid = True
                        else:
                            issues.append({**detail, 'path': str(path), 'status': 'copy_mismatch'})
                    except Exception as exc:
                        issues.append({**detail, 'path': loc.get('path'), 'status': 'copy_missing_or_unreadable', 'error': str(exc)})
                if valid and source_matches:
                    checked += 1
        managed_files = []
        try:
            managed_files = list(local_inventory(library, managed))
            managed_bytes = sum(p.stat().st_size for p in managed_files)
        except Exception as exc:
            managed_bytes = None
            issues.append({'status': 'managed_inventory_failed', 'error': str(exc)})
        return {'checked_at': now(), 'ok': not issues, 'verification': 'size' if quick else 'sha256',
                'sources': summaries, 'verified_item_count': checked,
                'managed': {'root': str(managed), 'file_count': len(managed_files), 'total_bytes': managed_bytes,
                            'compared_copy_count': len(destinations),
                            'compared_copy_bytes': sum(v['size_bytes'] for v in destinations.values())},
                'issues': issues}
