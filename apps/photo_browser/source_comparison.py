"""Compare two catalog scopes without opening originals or managed media."""
import re
from collections import Counter, defaultdict

from library import atomic_json, component, now, read_json, uid
from library_summary import location_keys


class SourceComparison:
    def __init__(self, library):
        self.library = library
        self.directory = library.db / 'source_comparisons'

    def path(self, comparison_id):
        return self.directory / (component(comparison_id) + '.json')

    @staticmethod
    def scope(value):
        if not isinstance(value, dict):
            raise ValueError('비교할 소스 ID와 카테고리를 지정하세요.')
        return {'source_id': component(value.get('source_id')),
                'category': component(value['category']) if value.get('category') else None}

    def compare(self, left, right, progress=None):
        left, right = self.scope(left), self.scope(right)
        if left == right:
            raise ValueError('서로 다른 소스 또는 카테고리를 선택하세요.')
        progress = progress or (lambda value: None)
        items = self.library.items()  # One immutable catalog generation.
        groups = defaultdict(lambda: {'left': [], 'right': []})
        paths = {side: {'source': defaultdict(set), 'managed': defaultdict(set)} for side in ('left', 'right')}
        totals, missing = Counter(), Counter()
        media_ids = {'left': set(), 'right': set()}
        for index, item in enumerate(items):
            if item['lifecycle']['status'] != 'active':
                continue
            sha = str(item.get('sha256') or '').lower()
            valid = bool(re.fullmatch('[0-9a-f]{64}', sha))
            for side, scope in (('left', left), ('right', right)):
                if scope['category'] and item['classification']['category_id'] != scope['category']:
                    continue
                sources = [loc for loc in item['locations'] if loc['role'] == 'source' and loc.get('source_id') == scope['source_id']]
                if not sources or item['media_id'] in media_ids[side]:
                    continue
                media_ids[side].add(item['media_id'])
                managed = [loc for loc in item['locations'] if loc['role'] == 'managed' and loc.get('status') == 'available']
                def describe(loc):
                    return {'path': loc.get('path') or loc.get('uri') or '', 'status': loc.get('status', 'unknown')}
                entry = {'media_id': item['media_id'], 'name': item['name'], 'category': item['classification']['category_id'],
                         'owner_id': item['classification']['owner_id'], 'source_paths': [describe(loc) for loc in sources],
                         'managed_paths': [describe(loc) for loc in managed]}
                key = (sha, item['size_bytes']) if valid else ('unknown', side, item['media_id'])
                groups[key][side].append(entry)
                totals[side] += 1
                missing[side] += any(loc.get('status') == 'missing' for loc in sources)
                for kind, locations in (('source', sources), ('managed', managed)):
                    for loc in locations:
                        file, _ = location_keys(loc)
                        if file is not None:
                            paths[side][kind][file].add(key)
            if index % 1000 == 0:
                progress({'phase': 'source_comparing', 'processed': index, 'total': len(items),
                          'percent': round(index * 100 / len(items), 1) if items else 100})
        shared_paths = {kind: paths['left'][kind].keys() & paths['right'][kind].keys() for kind in ('source', 'managed')}
        conflicts = set()
        for file in shared_paths['source']:
            known_left = {key for key in paths['left']['source'][file] if key[0] != 'unknown'}
            known_right = {key for key in paths['right']['source'][file] if key[0] != 'unknown'}
            if known_left and known_right and known_left != known_right:
                conflicts.add(file)
        conflict_keys = {key for file in conflicts for side in ('left', 'right') for key in paths[side]['source'][file]}
        rows, counts = [], Counter()
        for key, entries in groups.items():
            status = ('unknown' if key[0] == 'unknown' else 'same' if entries['left'] and entries['right']
                      else 'left_only' if entries['left'] else 'right_only')
            counts[status] += 1
            if status == 'same':
                counts['matched_left_items'] += len(entries['left'])
                counts['matched_right_items'] += len(entries['right'])
            rows.append({'status': status, 'sha256': key[0] if key[0] != 'unknown' else None,
                         'size_bytes': key[1] if key[0] != 'unknown' else None,
                         'source_path_conflict': key in conflict_keys, **entries})
        rows.sort(key=lambda row: (row['status'], row['sha256'] or '', row['size_bytes'] or 0))
        equal = bool(totals['left'] and totals['right'] and not any(counts[s] for s in ('unknown', 'left_only', 'right_only')))
        report = {'schema_version': 1, 'comparison_id': uid(), 'created_at': now(), 'left': left, 'right': right,
                  'left_items': totals['left'], 'right_items': totals['right'], 'missing_left_items': missing['left'],
                  'missing_right_items': missing['right'], 'counts': dict(counts), 'same_contents': equal,
                  'same_multiplicity': equal and all(len(row['left']) == len(row['right']) for row in rows),
                  'shared_media_ids': len(media_ids['left'] & media_ids['right']),
                  'shared_source_paths': len(shared_paths['source']), 'shared_managed_paths': len(shared_paths['managed']),
                  'conflicting_source_paths': len(conflicts), 'rows': rows,
                  'basis': '현재 DB의 활성 항목에 저장된 SHA-256·크기 비교입니다. 누락 표시 원본도 포함합니다. 실제 파일을 읽거나 해시를 재계산하지 않습니다. 동일 SHA-256은 동일 바이너리 기준이며 크기·편집이 다른 유사 사진은 별개입니다.'}
        atomic_json(self.path(report['comparison_id']), report)
        return {key: value for key, value in report.items() if key != 'rows'} | {'status': 'completed', 'row_count': len(rows)}

    def page(self, comparison_id, status='all', offset=0, limit=100):
        if status not in {'all', 'same', 'left_only', 'right_only', 'unknown', 'conflict'}:
            raise ValueError('올바른 비교 결과 구분을 선택하세요.')
        report = read_json(self.path(comparison_id))
        if not report:
            raise ValueError('비교 기록이 없습니다.')
        rows = [row for row in report['rows'] if status == 'all' or row['status'] == status
                or (status == 'conflict' and row['source_path_conflict'])]
        result = {key: value for key, value in report.items() if key != 'rows'}
        result.update(total=len(rows), offset=offset, limit=limit, rows=[])
        for row in rows[offset:offset + limit]:
            result['rows'].append({**row, 'left_count': len(row['left']), 'right_count': len(row['right']),
                                   'left': row['left'][:20], 'right': row['right'][:20]})
        return result
