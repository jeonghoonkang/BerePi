"""Copy-on-write catalog updates preserving unchanged immutable chunks."""
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
    publish_pages(library, manifest, entries, replacements, writes, minimum_free_bytes)
    return changed


def publish_pages(library, manifest, entries, replacements, writes, minimum_free_bytes=0):
    """Publish every replacement through one final atomic index switch."""
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


def merge_identity(item):
    """Merge may change managed locations/place labels, never content or grouping."""
    stable = copy.deepcopy(item)
    stable.pop('revision', None)
    stable['locations'] = [loc for loc in stable['locations'] if loc['role'] != 'managed']
    stable['capture'].pop('place', None)
    stable['classification'].pop('location_tags', None)
    return stable


def patch_merge_items(library, changes, minimum_free_bytes=0):
    """Caller holds writing(); changes contains the actual changed merge items."""
    if not changes:
        return 0
    manifest = read_json(library.db / 'index.json', {'chunks': []})
    with library.lookup_lock:
        library._ensure_lookup(manifest)
        lookup, entries = library.lookup_chunks, library.lookup_entries
    if set(changes) - lookup.keys():
        raise ValueError('병합 대상이 현재 인덱스에 없습니다. 다시 검사하세요.')
    by_chunk = {}
    for mid, item in changes.items():
        if not isinstance(item, dict) or item.get('media_id') != mid:
            raise ValueError('병합 부분 저장의 미디어 ID가 올바르지 않습니다.')
        by_chunk.setdefault(lookup[mid], {})[mid] = item
    generation = uid()
    replacements, writes, changed = {}, [], 0
    for path, updates in by_chunk.items():
        page = read_json(library.db / path)
        dirty = False
        for index, before in enumerate(page['items']):
            if before['media_id'] not in updates:
                continue
            item = copy.deepcopy(updates[before['media_id']])
            if merge_identity(before) != merge_identity(item):
                raise ValueError('병합 부분 저장은 원본·파일 내용·분류·촬영 날짜·상태 변경을 허용하지 않습니다.')
            c = item['classification']
            if 'no_gps' in c.get('tags', []) and gps_coordinates(item['capture']) is not None:
                c['tags'] = [tag for tag in c['tags'] if tag != 'no_gps']
            c['location_tags'] = capture_location_tags(item['capture'])
            if item != before:
                page['items'][index] = item
                dirty = True
                changed += 1
        if dirty:
            relative = str(PurePosixPath(path).parent / f'media_{generation}_{len(writes) + 1:06d}.json')
            replacements[path] = chunk_entry(relative, page['items'])
            writes.append((relative, page))
    if writes:
        # SHA-256/capture coordinates/lifecycle are unchanged, so retain the
        # existing duplicate index as well as every untouched media page.
        publish_pages(library, manifest, entries, replacements, writes, minimum_free_bytes)
    return changed


def estimate_merge_growth(library, pending_count, dirty):
    """Conservative cumulative growth of touched pages, indexes and job records."""
    manifest = read_json(library.db / 'index.json', {'chunks': []})
    with library.lookup_lock:
        library._ensure_lookup(manifest)
        lookup, entries = library.lookup_chunks, library.lookup_entries
    sizes, pairs = {}, set()
    for position, item in dirty:
        path = lookup.get(item['media_id'], 'unindexed:' + item['media_id'])
        if path not in sizes:
            if path in entries:
                sizes[path] = (library.db / path).stat().st_size + entries[path]['count'] * 4096
            else:
                sizes[path] = (len(json.dumps(item, ensure_ascii=False, indent=2).encode()) + 4096) * 100
        pairs.add((position // 25, path))
    # One extra rewrite per touched page covers resumed checkpoint alignment
    # and the final publication. Unrelated pages contribute no write bytes.
    page_writes = len(pairs) + len(sizes)
    page_bytes = sum(sizes[path] for _, path in pairs) + sum(sizes.values())
    index_path = library.db / 'index.json'
    index_bytes = (index_path.stat().st_size if index_path.exists() else 0) + len(manifest['chunks']) * 128
    publications = len({position for position, _ in pairs}) + 2 if pairs else 0
    # index.json is replaced in place; only its temporary replacement needs
    # simultaneous capacity, rather than retaining one index per checkpoint.
    estimate = page_bytes + index_bytes * (2 if pairs else 0) + pending_count * 8192 + 2 * 1024 * 1024
    return {'db_estimated_bytes': estimate, 'estimated_chunk_writes': page_writes,
            'estimated_touched_chunks': len(sizes), 'estimated_index_publications': publications,
            'db_estimate_model': 'copy_on_write_chunks'}
