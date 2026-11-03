"""Current-generation DB inventory grouped by source, category and owner."""
import json
import threading
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from library import now, read_json


def location_keys(location):
    """Stable recorded file/parent identities; never touch source disks/network."""
    uri = location.get('uri')
    if uri:
        parsed = urlsplit(uri)
        prefix = (parsed.scheme.lower(), parsed.netloc.lower())
        return (*prefix, parsed.path), (*prefix, str(PurePosixPath(parsed.path).parent))
    path = location.get('path')
    if path:
        path = path.replace('\\', '/')
        return ('file', '', path), ('file', '', str(PurePosixPath(path).parent))
    return None, None


class Counts:
    def __init__(self):
        self.items = {}
        self.source_files, self.source_dirs = set(), set()
        self.managed_files, self.managed_dirs = set(), set()
        self.missing_files = set()

    def add(self, item, source_locations, managed_locations):
        self.items[item['media_id']] = item['size_bytes']
        for location in source_locations:
            file, directory = location_keys(location)
            if file is not None:
                self.source_files.add(file)
                self.source_dirs.add(directory)
                if location.get('status') == 'missing':
                    self.missing_files.add(file)
        for location in managed_locations:
            file, directory = location_keys(location)
            if file is not None:
                self.managed_files.add(file)
                self.managed_dirs.add(directory)

    def result(self):
        return {'media_count': len(self.items), 'media_bytes': sum(self.items.values()),
                'source_file_count': len(self.source_files), 'source_directory_count': len(self.source_dirs),
                'managed_file_count': len(self.managed_files), 'managed_directory_count': len(self.managed_dirs),
                'missing_source_file_count': len(self.missing_files)}


class LibrarySummary:
    def __init__(self, library):
        self.library = library
        self.lock = threading.Lock()
        self.generation = None
        self.cached = None

    def snapshot(self, refresh=False):
        config = self.library.config()
        index = read_json(self.library.db / 'index.json', {'chunks': []})
        key = (json.dumps(config, ensure_ascii=False, sort_keys=True), index.get('updated_at'),
               tuple(c['path'] for c in index['chunks']))
        with self.lock:
            if not refresh and key == self.generation:
                return {**self.cached, 'cached': True}
            configured = {s['source_id']: s for s in config.get('sources', [])}
            sources = {}
            groups = {}
            total = Counts()
            catalog_sources = set()
            categories, owners, inactive = set(), set(), set()

            def source_row(sid):
                if sid not in sources:
                    source = configured.get(sid)
                    sources[sid] = {'source_id': sid, 'registered': source is not None,
                                    'root': source.get('root') if source else None,
                                    'protocol': source.get('protocol', 'file') if source else None,
                                    'configured_category_ids': [source.get('category', 'family')] if source else [],
                                    'configured_owner_ids': [source.get('owner_id', 'default')] if source else [],
                                    'categories': set(), 'owners': set(), 'inactive': set(), 'counts': Counts()}
                return sources[sid]

            for sid in configured:
                source_row(sid)
            for chunk in index['chunks']:
                # Old generations, journals and reports are not current catalog entries.
                value = read_json(self.library.db / chunk['path'])
                if not isinstance(value, dict) or not isinstance(value.get('items'), list):
                    raise ValueError(f'현재 DB 청크를 읽지 못했습니다: {chunk["path"]}')
                for item in value['items']:
                    by_source = {}
                    for location in item['locations']:
                        if location['role'] == 'source' and location.get('source_id'):
                            sid = location['source_id']
                            catalog_sources.add(sid)
                            source_row(sid)
                            by_source.setdefault(sid, []).append(location)
                    if item['lifecycle']['status'] != 'active':
                        inactive.add(item['media_id'])
                        for sid in by_source:
                            sources[sid]['inactive'].add(item['media_id'])
                        continue
                    classification = item['classification']
                    category, owner = classification['category_id'], classification['owner_id']
                    categories.add(category)
                    owners.add(owner)
                    managed = [loc for loc in item['locations'] if loc['role'] == 'managed' and loc.get('status') == 'available']
                    total.add(item, [loc for values in by_source.values() for loc in values], managed)
                    # A source can already contain many category/owner pairs because
                    # individual items may have been reclassified after scanning.
                    for sid, locations in by_source.items():
                        source = sources[sid]
                        source['categories'].add(category)
                        source['owners'].add(owner)
                        source['counts'].add(item, locations, managed)
                        groups.setdefault((sid, category, owner), Counts()).add(item, locations, managed)
                    if not by_source:
                        # Keep orphan catalog items visible, not silently dropped.
                        groups.setdefault((None, category, owner), Counts()).add(item, [], managed)

            rows = []
            for sid, row in sorted(sources.items()):
                rows.append({key: value for key, value in row.items() if key not in {'categories', 'owners', 'inactive', 'counts'}} |
                            {'category_ids': sorted(row['categories']), 'owner_ids': sorted(row['owners']),
                             'inactive_media_count': len(row['inactive']), **row['counts'].result()})
            data = {'schema_version': 1, 'observed_at': now(), 'db': str(self.library.db),
                    'managed_root': config['managed_root'], 'index_updated_at': index.get('updated_at'),
                    'current_chunk_count': len(index['chunks']), 'source_count': len(sources),
                    'configured_source_count': len(configured), 'catalog_source_count': len(catalog_sources),
                    'category_ids': sorted(categories), 'owner_ids': sorted(owners),
                    'inactive_media_count': len(inactive), 'totals': total.result(), 'sources': rows,
                    'groups': [{'source_id': sid, 'category_id': category, 'owner_id': owner, **counts.result()}
                               for (sid, category, owner), counts in sorted(groups.items(), key=lambda pair: tuple(v or '' for v in pair[0]))],
                    'note': '현재 index.json의 청크 전체를 집계한 DB 기록입니다. 비활성 항목은 별도 집계하고, 디렉토리는 파일의 고유 직계 부모 경로 수입니다. 실제 디스크 검사·빈 폴더 집계는 하지 않습니다. 공유 항목은 여러 행에 포함될 수 있어 행 합계와 전체 고유 합계는 다를 수 있습니다.'}
            self.generation, self.cached = key, data
            return {**data, 'cached': False}
