"""Reversible, scoped duplicate catalog archiving. Never changes media files."""
import copy
import hashlib
import json
import re
from collections import Counter, defaultdict

from library import atomic_json, component, now, read_json, uid
from source_comparison import SourceComparison


class DuplicateCleanup:
    def __init__(self, library):
        self.library = library
        self.directory = library.db / 'duplicate_cleanups'

    def path(self, operation_id):
        return self.directory / (component(operation_id) + '.json')

    @staticmethod
    def signature(value):
        return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def scope(value):
        scope = SourceComparison.scope(value)
        if not scope['category']:
            raise ValueError('DB 정리에는 소스 ID와 특정 카테고리를 모두 선택해야 합니다.')
        return scope

    @staticmethod
    def selected(items, scope):
        return [item for item in items if item['lifecycle']['status'] == 'active'
                and item['classification']['category_id'] == scope['category']
                and any(loc['role'] == 'source' and loc.get('source_id') == scope['source_id'] for loc in item['locations'])]

    @staticmethod
    def content_key(item):
        sha = str(item.get('sha256') or '').lower()
        return (sha, item['size_bytes']) if re.fullmatch('[0-9a-f]{64}', sha) else None

    def scope_signature(self, items):
        return self.signature(sorted((item['media_id'], self.signature(item)) for item in items))

    def load(self, operation_id):
        record = read_json(self.path(operation_id))
        if not record:
            raise ValueError('중복 DB 정리 기록이 없습니다.')
        return record

    def save(self, record):
        record['updated_at'] = now()
        atomic_json(self.path(record['operation_id']), record)

    @staticmethod
    def overview(record):
        return {key: value for key, value in record.items() if key not in {'changes'}} | {
            'total': record['remove_items'], 'processed': record['remove_items'], 'percent': 100}

    def records(self):
        return sorted((self.overview(read_json(path)) for path in self.directory.glob('*.json')),
                      key=lambda record: record['created_at'], reverse=True)

    def preview(self, remove, keep):
        remove, keep = self.scope(remove), self.scope(keep)
        if remove == keep:
            raise ValueError('정리할 범위와 유지할 범위는 달라야 합니다.')
        with self.library.writing():
            items = self.library.items()
            selected, retained = self.selected(items, remove), self.selected(items, keep)
            if not selected or not retained:
                raise ValueError('정리할 범위와 유지할 범위에 활성 DB 항목이 있어야 합니다.')
            by_content = defaultdict(list)
            keep_ids = {item['media_id'] for item in retained}
            for item in sorted(retained, key=lambda item: item['media_id']):
                key = self.content_key(item)
                if key:
                    by_content[key].append(item)
            operation_id, changes, skipped = uid(), [], Counter()
            preserved_categories = Counter(item['classification']['category_id'] for item in items
                                           if item['lifecycle']['status'] == 'active'
                                           and item['classification']['category_id'] != remove['category']
                                           and any(loc['role'] == 'source' and loc.get('source_id') == remove['source_id']
                                                   for loc in item['locations']))
            for item in selected:
                key = self.content_key(item)
                if item['media_id'] in keep_ids:
                    skipped['shared_item'] += 1
                elif any(loc['role'] == 'source' and loc.get('source_id') != remove['source_id'] for loc in item['locations']):
                    skipped['shared_source'] += 1
                elif not key:
                    skipped['unknown_hash'] += 1
                elif key not in by_content:
                    skipped['no_duplicate'] += 1
                else:
                    keeper = next((other for other in by_content[key]
                                   if other['classification']['owner_id'] == item['classification']['owner_id']), by_content[key][0])
                    after = copy.deepcopy(item)
                    after['lifecycle'] = {'status': 'duplicate_archived', 'cleanup_id': operation_id,
                                          'duplicate_of': keeper['media_id'], 'archived_at': now()}
                    after['revision'] = item.get('revision', 0) + 1
                    changes.append({'before': copy.deepcopy(item), 'after': after, 'keeper_id': keeper['media_id']})
            record = {'schema_version': 1, 'operation_id': operation_id, 'created_at': now(), 'status': 'preview',
                      'remove': remove, 'keep': keep, 'remove_items': len(selected), 'keep_items': len(retained),
                      'remove_signature': self.scope_signature(selected), 'keep_signature': self.scope_signature(retained),
                      'archive_count': len(changes), 'skipped': dict(skipped), 'changes': changes,
                      'preserved_categories': [{'category': category, 'count': count} for category, count in sorted(preserved_categories.items())],
                      'basis': 'DB에 저장된 SHA-256·크기가 같은 별도 항목만 비활성 보관합니다. 실제 파일을 검증하거나 삭제하지 않습니다. 원본·관리 파일, 유지측 항목·태그, 다른 카테고리와 소스 설정은 변경하지 않습니다.'}
            self.save(record)
            return self.overview(record)

    def database_state(self, record, items):
        current = {item['media_id']: item for item in items}
        before = after = True
        for change in record['changes']:
            item = current.get(change['before']['media_id'])
            before &= self.signature(item) == self.signature(change['before'])
            after &= self.signature(item) == self.signature(change['after'])
        if before:
            return 'before'
        if after:
            return 'after'
        raise ValueError('대상 DB 항목이 변경되었습니다. 기존 기록으로 덮어쓸 수 없습니다. 새 미리보기 또는 변경 내역 확인이 필요합니다.')

    def execute(self, operation_id):
        with self.library.writing():
            record = self.load(operation_id)
            if record['status'] == 'completed':
                return self.overview(record)
            if record['status'] not in {'preview', 'applying'} or not record['changes']:
                raise ValueError('실행 가능한 중복 DB 정리 계획이 없습니다.')
            items = self.library.items()
            if self.database_state(record, items) == 'before':
                if (self.scope_signature(self.selected(items, record['remove'])) != record['remove_signature']
                        or self.scope_signature(self.selected(items, record['keep'])) != record['keep_signature']):
                    raise ValueError('선택 범위의 DB가 변경되었습니다. 새 미리보기를 실행하세요.')
                record['status'] = 'applying'
                self.save(record)  # Durable undo snapshots before the atomic catalog commit.
                updates = {change['after']['media_id']: change['after'] for change in record['changes']}
                self.library.commit([copy.deepcopy(updates.get(item['media_id'], item)) for item in items], normalize_metadata=False)
            record.update(status='completed', finished_at=now())
            self.save(record)
            return self.overview(record)

    def undo(self, operation_id):
        with self.library.writing():
            record = self.load(operation_id)
            if record['status'] == 'undone':
                return self.overview(record)
            if record['status'] not in {'completed', 'applying', 'undoing'} or not record['changes']:
                raise ValueError('되돌릴 중복 DB 정리 작업이 없습니다.')
            items = self.library.items()
            if self.database_state(record, items) == 'after':
                record['status'] = 'undoing'
                self.save(record)
                updates = {change['before']['media_id']: change['before'] for change in record['changes']}
                self.library.commit([copy.deepcopy(updates.get(item['media_id'], item)) for item in items], normalize_metadata=False)
            record.update(status='undone', undone_at=now())
            self.save(record)
            return self.overview(record)

    def page(self, operation_id, offset=0, limit=100):
        record = self.load(operation_id)
        result = self.overview(record)
        result.update(offset=offset, total=len(record['changes']), rows=[])
        for change in record['changes'][offset:offset + limit]:
            item = change['before']
            result['rows'].append({'media_id': item['media_id'], 'keeper_id': change['keeper_id'],
                                   'name': item['name'], 'sha256': item['sha256'], 'size_bytes': item['size_bytes'],
                                   'owner_id': item['classification']['owner_id'], 'locations': item['locations'],
                                   'classification': item['classification']})
        return result
