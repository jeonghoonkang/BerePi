"""Cross-source/category/owner exact matches detected while scanning."""
import json
from collections import defaultdict

from library import component


def source_ids(item):
    return sorted({loc['source_id'] for loc in item['locations']
                   if loc['role'] == 'source' and loc.get('source_id')})


class ScanDuplicateIndex:
    def __init__(self, library, items):
        self.library = library
        self.hashes = defaultdict(dict)
        self.previous = {}
        for item in items:
            self.add(item)

    def add(self, item):
        mid = item['media_id']
        old = self.previous.pop(mid, None)
        if old:
            self.hashes[old].pop(mid, None)
        if item['lifecycle']['status'] == 'active' and item.get('sha256'):
            self.hashes[item['sha256']][mid] = item
            self.previous[mid] = item['sha256']

    def check(self, item):
        c = item['classification']
        sources = source_ids(item)
        matches, total = [], 0
        for other in self.hashes.get(item['sha256'], {}).values():
            if other['media_id'] == item['media_id'] or other['size_bytes'] != item['size_bytes']:
                continue
            old = other['classification']
            ids = source_ids(other)
            if (old['category_id'], old['owner_id'], ids) == (c['category_id'], c['owner_id'], sources):
                continue
            total += 1
            if len(matches) >= 50:
                continue
            managed = []
            for loc in other['locations']:
                if loc['role'] != 'managed' or loc.get('status') != 'available' or not loc.get('path'):
                    continue
                try:
                    exists = self.library.local(loc['path']).is_file()
                except (OSError, ValueError):
                    exists = None
                managed.append({'path': loc['path'], 'exists': exists})
            matches.append({'media_id': other['media_id'], 'name': other['name'],
                            'category_id': old['category_id'], 'owner_id': old['owner_id'],
                            'source_ids': ids, 'managed_files': managed})
        if not total:
            return None
        loc = next((loc for loc in item['locations'] if loc['role'] == 'source'), {})
        return {'media_id': item['media_id'], 'source_file': loc.get('path') or loc.get('uri') or item['name'],
                'sha256': item['sha256'], 'category_id': c['category_id'], 'owner_id': c['owner_id'],
                'match_count': total, 'matches': matches, 'matches_truncated': total > len(matches)}


def duplicate_page(library, scan_id, offset=0):
    path = library.db / 'scans' / 'sessions' / component(scan_id) / 'results.jsonl'
    if not path.is_file():
        raise FileNotFoundError('스캔 결과가 없습니다.')
    rows, total = [], 0
    with path.open('rb') as stream:
        for line in stream:
            if not line.endswith(b'\n'):
                break  # A running scan may still be writing the final record.
            record = json.loads(line)
            match = record.get('duplicate_check')
            if match:
                if offset <= total < offset + 100:
                    rows.append(match)
                total += 1
    return {'scan_id': scan_id, 'items': rows, 'total': total, 'offset': offset, 'limit': 100}
