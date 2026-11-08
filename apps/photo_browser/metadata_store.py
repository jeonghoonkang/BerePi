"""Copy-on-write catalog updates for classification tags and place names only."""
import copy
import json
import shutil
from pathlib import PurePosixPath

from library import (FACET_FIELDS, atomic_json, capture_location_tags, facet_values,
                     gps_coordinates, now, read_json, uid)


def chunk_entry(path, items):
    active = [item for item in items if item['lifecycle']['status'] == 'active']
    return {'path': path, 'count': len(items), 'media_ids': [item['media_id'] for item in items],
            'first_date': items[0]['capture']['date_key'], 'last_date': items[-1]['capture']['date_key'],
            'facets': {key: sorted({value for item in items for value in facet_values(item, key)}) for key in FACET_FIELDS},
            'active_facets': {key: sorted({value for item in active for value in facet_values(item, key)}) for key in FACET_FIELDS}}


def patch_metadata(library, changes, minimum_free_bytes=0):
    """Caller owns library.writing(); publish all new pages through one manifest."""
    if not changes:
        return 0
    allowed = {'tags', 'events', 'person_ids', 'place'}
    for patch in changes.values():
        if not isinstance(patch, dict) or set(patch) - allowed:
            raise ValueError('부분 저장은 태그와 위치 이름 정보만 지원합니다.')
    manifest = read_json(library.db / 'index.json', {'chunks': []})
    with library.lookup_lock:
        library._ensure_lookup(manifest)
        lookup, entries = library.lookup_chunks, library.lookup_entries
    by_chunk = {}
    for mid, patch in changes.items():
        if mid in lookup:
            by_chunk.setdefault(lookup[mid], {})[mid] = patch
    generation = uid()
    replacements, writes = {}, []
    changed = 0
    for path, patches in by_chunk.items():
        page = read_json(library.db / path)
        dirty = False
        for item in page['items']:
            patch = patches.get(item['media_id'])
            if patch is None:
                continue
            before = copy.deepcopy(item)
            for key, value in patch.items():
                if key == 'place':
                    item['capture']['place'] = copy.deepcopy(value)
                else:
                    item['classification'][key] = copy.deepcopy(value)
            c = item['classification']
            if 'no_gps' in c.get('tags', []) and gps_coordinates(item['capture']) is not None:
                c['tags'] = [tag for tag in c['tags'] if tag != 'no_gps']
            c['location_tags'] = capture_location_tags(item['capture'])
            if item != before:
                item['revision'] = before['revision'] + 1
                changed += 1
                dirty = True
        if dirty:
            # Preserve membership/order, so a small edit never shifts later pages.
            relative = str(PurePosixPath(path).parent / f'media_{generation}_{len(writes) + 1:06d}.json')
            replacements[path] = chunk_entry(relative, page['items'])
            writes.append((relative, page))
    if not writes:
        return 0
    chunks = [replacements.get(entry['path'], entries[entry['path']]) for entry in manifest['chunks']]
    active_facets = {key: sorted({value for entry in chunks for value in entry['active_facets'][key]}) for key in FACET_FIELDS}
    updated = {**manifest, 'chunks': chunks, 'active_facets': active_facets, 'updated_at': now()}
    if minimum_free_bytes:
        estimate = sum(len(json.dumps(page, ensure_ascii=False, indent=2).encode()) for _, page in writes)
        estimate += len(json.dumps(updated, ensure_ascii=False, indent=2).encode()) + 2 * 1024 * 1024
        if shutil.disk_usage(library.db).free < minimum_free_bytes + estimate:
            raise ValueError('DB 저장 공간이 부족합니다. 공간 확보 후 다시 실행하세요. 조회 캐시는 유지됩니다.')
    for relative, page in writes:
        atomic_json(library.db / relative, page)
    # Coordinates, dates, content and membership did not change: reuse duplicates.
    atomic_json(library.db / 'index.json', updated)
    return changed
