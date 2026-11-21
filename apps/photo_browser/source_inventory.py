"""Metadata-only first pass before per-file hashes are compared."""
import hashlib
import json
from collections import Counter
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit


def inventory_size(library, source, info):
    if source.get('protocol', 'file') == 'file':
        try:
            return library.local(info['path']).stat().st_size
        except (OSError, ValueError, KeyError):
            return None
    value = info.get('size_bytes', info.get('size'))
    try:
        return int(value) if not isinstance(value, bool) and int(value) >= 0 else None
    except (ValueError, TypeError):
        return None


def relative_name(source, uri):
    if source.get('protocol', 'file') == 'file':
        return Path(unquote(urlsplit(uri).path)).relative_to(Path(source['root'])).as_posix()
    base, target = urlsplit(source['root']), urlsplit(uri)
    prefix = unquote(base.path).rstrip('/') + '/'
    path = unquote(target.path)
    if (base.scheme, base.netloc) != (target.scheme, target.netloc) or not path.startswith(prefix):
        raise ValueError('소스 범위 밖의 파일입니다.')
    name = path[len(prefix):]
    if '..' in PurePosixPath(name).parts:
        raise ValueError('상대 경로가 올바르지 않습니다.')
    return name


def profile(source, files):
    directories = Counter()
    parents = {'.'}
    total = unknown = invalid = count = 0
    for uri, size in files:
        count += 1
        if size is None:
            unknown += 1
        else:
            total += size
        try:
            directory = PurePosixPath(relative_name(source, uri)).parent
            directories[directory.as_posix()] += 1
            parents.update(parent.as_posix() for parent in (directory, *directory.parents))
        except (ValueError, OSError):
            invalid += 1
    signature = hashlib.sha256(json.dumps(sorted(directories.items()), ensure_ascii=False).encode()).hexdigest()
    return {'file_count': count, 'total_bytes': total if not unknown else None,
            'known_bytes': total, 'unknown_size_files': unknown,
            'directory_count': len(parents), 'relative_path_errors': invalid,
            'structure_fingerprint': signature, 'complete': not unknown and not invalid}


def compare_source_inventory(library, source, entries, items):
    current = profile(source, ((entry['uri'], entry['size_bytes'] if 'size_bytes' in entry else inventory_size(library, source, entry['info'])) for entry in entries))
    sources = {entry['source_id']: entry for entry in library.config()['sources']}
    recorded = {sid: {} for sid in sources if sid != source['source_id']}
    for item in items:
        if item['lifecycle']['status'] != 'active':
            continue
        for loc in item['locations']:
            sid = loc.get('source_id')
            if loc['role'] == 'source' and sid in recorded and loc.get('status') not in {'missing', 'inactive'}:
                recorded[sid][loc['uri']] = item['size_bytes']
    comparisons = []
    for sid, files in sorted(recorded.items()):
        previous = profile(sources[sid], files.items())
        if not files or not current['complete'] or not previous['complete']:
            status = 'insufficient_inventory'
        elif all(current[key] == previous[key] for key in ('file_count', 'total_bytes', 'structure_fingerprint')):
            status = 'same_layout_candidate'
        else:
            status = 'different_source'
        comparisons.append({'source_id': sid, 'status': status, **previous})
    return {'current': current, 'comparisons': comparisons,
            'same_layout_count': sum(row['status'] == 'same_layout_candidate' for row in comparisons),
            'different_source_count': sum(row['status'] == 'different_source' for row in comparisons),
            'unknown_count': sum(row['status'] == 'insufficient_inventory' for row in comparisons)}
