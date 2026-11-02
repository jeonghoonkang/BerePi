"""Reclassify managed media with verified copies and a recoverable journal."""
import copy
import hashlib
import json
import os
import shutil
from pathlib import Path

from library import atomic_json, component, digest, now, read_json, uid


class CategoryMerger:
    def __init__(self, library):
        self.library = library
        self.directory = library.db / 'category_merges'

    def record_path(self, operation_id):
        return self.directory / (component(operation_id) + '.json')

    def load(self, operation_id):
        record = read_json(self.record_path(operation_id))
        if not record:
            raise ValueError('카테고리 통합 기록이 없습니다.')
        if self.library.local(self.library.config()['managed_root']) != self.library.local(record['managed_root']):
            raise ValueError('관리 디렉토리가 변경되었습니다. 이전 통합 작업을 실행할 수 없습니다.')
        journal = self.record_path(operation_id).with_suffix('.jsonl')
        if journal.exists():
            moves = {move['original']: move for move in record['moves']}
            with journal.open('rb') as stream:
                for line in stream:
                    if not line.endswith(b'\n'):
                        break  # A torn final record is retried on resume.
                    event = json.loads(line)
                    if 'row_index' in event:
                        record['rows'][event['row_index']] = event['row']
                        created = event.get('created')
                        if created and created not in record['created_files']:
                            record['created_files'].append(created)
                    if 'move' in event:
                        moves[event['move']['original']] = event['move']
            record['moves'] = list(moves.values())
        return record

    def journal(self, record, event):
        path = self.record_path(record['operation_id']).with_suffix('.jsonl')
        # Repair an interrupted final append before writing the retry record.
        if path.exists():
            with path.open('r+b') as stream:
                stream.seek(0, 2)
                length = stream.tell()
                if length:
                    stream.seek(-1, 2)
                    if stream.read(1) != b'\n':
                        stream.seek(0)
                        data = stream.read()
                        stream.truncate(data.rfind(b'\n') + 1)
        with path.open('ab') as stream:
            stream.write((json.dumps(event, ensure_ascii=False) + '\n').encode())
            stream.flush()
            os.fsync(stream.fileno())

    def save(self, record):
        record['updated_at'] = now()
        atomic_json(self.record_path(record['operation_id']), record)

    def records(self):
        return sorted((read_json(path) for path in self.directory.glob('*.json')),
                      key=lambda item: item['created_at'], reverse=True)

    def root(self, record=None):
        return self.library.local(record['managed_root'] if record else self.library.config()['managed_root'])

    def checked(self, value, root):
        # Check the lexical path as well as its resolved boundary; links must
        # never be moved or used as verified managed originals.
        raw = Path(value)
        path = self.library.local(value)
        if raw.is_symlink() or not path.is_relative_to(root) or path == root:
            raise ValueError(f'관리 경계 밖이거나 링크인 경로입니다: {value}')
        return path

    def verify(self, path, sha, size):
        if path.is_symlink() or not path.is_file() or path.stat().st_size != size or digest(path) != sha:
            raise ValueError(f'관리 파일이 없거나 내용이 변경되었습니다: {path}')

    @staticmethod
    def signature(item):
        return hashlib.sha256(json.dumps(item, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def emit(self, record, progress, phase, path='', role='merge_destination', **extra):
        done = record.get('processed', 0)
        total = record.get('total_count', len(record['rows']))
        progress({'phase': phase, 'total': total, 'processed': done,
                  'percent': round(done * 100 / total, 1) if total else 0,
                  'inventory_complete': True, 'operation_id': record['operation_id'],
                  'current_file': str(path), 'current_file_role': role, 'current_action': phase, **extra})

    def preview(self, categories, target_category, progress=None):
        progress = progress or (lambda state: None)
        if not isinstance(categories, list) or not categories or len(categories) > 100 or any(not isinstance(c, str) for c in categories):
            raise ValueError('통합할 카테고리를 1~100개 선택하세요.')
        categories = list(dict.fromkeys(component(c) for c in categories))
        target_category = component(target_category)
        if target_category in categories:
            categories.remove(target_category)
        if not categories:
            raise ValueError('대상과 다른 카테고리를 하나 이상 선택하세요.')
        with self.library.writing():
            root = self.root()
            items = self.library.items()
            selected = [item for item in items if item['lifecycle']['status'] == 'active'
                        and item['classification']['category_id'] in categories]
            if not selected:
                raise ValueError('선택한 카테고리에 활성 사진이 없습니다.')
            record = {'schema_version': 1, 'operation_id': uid(), 'created_at': now(), 'status': 'preview',
                      'stage': 'preview', 'managed_root': str(root), 'source_categories': categories,
                      'target_category': target_category, 'total_count': len(selected), 'rows': [], 'moves': [], 'created_files': [], 'processed': 0}
            reserved, hashes = {}, {}
            for item in selected:
                done = len(record['rows'])
                self.emit(record, progress, 'category_planning', item['name'], 'managed_file',
                          processed=done, percent=round(done * 100 / len(selected), 1))
                candidates = [loc for loc in reversed(item['locations']) if loc['role'] == 'managed' and loc.get('status') == 'available']
                source = None
                for location in candidates:
                    path = self.checked(location['path'], root)
                    if path.is_relative_to(root / '.trash'):
                        continue
                    if path.is_file() and path.stat().st_size == item['size_bytes'] and digest(path) == item['sha256']:
                        source = path
                        break
                if source is None:
                    raise ValueError(f"검증된 managed 복사본이 없습니다. 원본 source는 읽지 않습니다: {item['name']}")
                after = copy.deepcopy(item)
                after['classification']['category_id'] = target_category
                target = self.library.resolve_merge_target(root, after, reserved, hashes)
                record['rows'].append({'before': copy.deepcopy(item), 'source': str(source),
                                       'destination': str(target), 'renamed': target.name != item['name']})
            record['processed'] = 0
            targets = {row['destination']: row['before']['size_bytes'] for row in record['rows'] if not Path(row['destination']).exists()}
            record['copy_files'] = len(targets)
            record['copy_bytes'] = sum(targets.values())
            record['warning'] = '검증 후 이전 관리 파일은 .trash/category-merges에 보관합니다. 원본·소스 설정은 변경하지 않으며 보관 파일도 공간을 사용합니다.'
            self.save(record)
            self.emit(record, progress, 'category_planning', processed=len(selected), percent=100)
            return record

    def ensure_space(self, record):
        root = self.root(record)
        pending = {row['destination']: row['before']['size_bytes'] for row in record['rows'] if not Path(row['destination']).exists()}
        reserve = self.library.config().get('scan_min_free_mb', 512) * 1048576
        # Include a conservative allowance for a new DB generation and journal.
        metadata = sum(len(json.dumps(item, ensure_ascii=False).encode()) + 4096 for item in self.library.items()) * 3
        if root.stat().st_dev == self.library.db.stat().st_dev:
            enough = shutil.disk_usage(root).free >= reserve + sum(pending.values()) + metadata
        else:
            enough = (shutil.disk_usage(root).free >= reserve + sum(pending.values())
                      and shutil.disk_usage(self.library.db).free >= reserve + metadata)
        if not enough:
            raise ValueError('카테고리 통합을 위한 복사·DB 저장 디스크 공간이 부족합니다.')

    def copy_checked(self, source, target, sha, size, reserve):
        self.verify(source, sha, size)
        if target.exists():
            self.verify(target, sha, size)
            return False
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name('.' + uid() + '.part')
        try:
            with source.open('rb') as incoming, temporary.open('xb') as output:
                for block in iter(lambda: incoming.read(1048576), b''):
                    if shutil.disk_usage(target.parent).free < reserve + len(block):
                        raise ValueError('복사 중 디스크 공간이 부족합니다.')
                    output.write(block)
            shutil.copystat(source, temporary)
            self.verify(temporary, sha, size)
            self.verify(source, sha, size)
            try:
                self.library.publish_merge_copy(temporary, target)
                return True
            except FileExistsError:
                self.verify(target, sha, size)
                return False
        finally:
            temporary.unlink(missing_ok=True)

    def move_checked(self, original, saved, sha, size):
        if saved.exists():
            self.verify(saved, sha, size)
        elif original.exists():
            self.verify(original, sha, size)
            saved.parent.mkdir(parents=True, exist_ok=True)
            self.library.publish_merge_copy(original, saved)
            self.verify(saved, sha, size)
        else:
            raise ValueError(f'복구할 관리 파일이 없습니다: {original}')
        if original.exists():
            self.verify(original, sha, size)
            original.unlink()

    def database_state(self, record, items):
        current = {item['media_id']: item for item in items}
        def matches(key):
            return all(row.get(key) and row['before']['media_id'] in current and
                       self.signature(current[row['before']['media_id']]) == self.signature(row[key]) for row in record['rows'])
        if matches('after'):
            return 'after'
        if matches('before'):
            return 'before'
        raise ValueError('미리보기 이후 사진 분류·태그·위치 또는 상태가 변경되었습니다. 진행 중 기록은 보존됩니다. 새 미리보기 또는 수동 복구가 필요합니다.')

    def protected_paths(self, items):
        # Include inactive/trash items and physical originals, not just active
        # managed references. A shared byte file must remain accessible.
        # Original sources can remain outside a restored server's boundary.
        # These are comparison keys only; do not read those source paths.
        return {str(Path(loc['path']).expanduser().resolve()) for item in items for loc in item['locations'] if loc.get('path')}

    def execute(self, operation_id, progress=None, stopped=None):
        progress, stopped = progress or (lambda state: None), stopped or (lambda: False)
        with self.library.writing():
            record = self.load(operation_id)
            if record['status'] == 'undone' or record['stage'].startswith('undo'):
                raise ValueError('되돌리기 상태의 작업은 통합 이어하기를 할 수 없습니다.')
            if record['status'] == 'completed':
                return record
            root = self.root(record)
            reserve = self.library.config().get('scan_min_free_mb', 512) * 1048576
            try:
                items = self.library.items()
                db_state = self.database_state(record, items)
                if db_state == 'before':
                    expected = {row['before']['media_id'] for row in record['rows']}
                    actual = {item['media_id'] for item in items if item['lifecycle']['status'] == 'active' and item['classification']['category_id'] in record['source_categories']}
                    if actual != expected:
                        raise ValueError('카테고리의 사진 목록이 변경되었습니다. 새 미리보기를 실행하세요.')
                    self.ensure_space(record)
                    record.update(status='running', stage='copying', processed=0)
                    self.save(record)
                    reserved, hashes = {}, {}
                    for row_index, row in enumerate(record['rows']):
                        if stopped():
                            record['status'] = 'stopped'
                            self.save(record)
                            return record
                        item = copy.deepcopy(row['before'])
                        item['classification']['category_id'] = record['target_category']
                        target = self.library.resolve_merge_target(root, item, reserved, hashes)
                        source = self.checked(row['source'], root)
                        row['destination'] = str(target)
                        row['renamed'] = target.name != item['name']
                        self.emit(record, progress, 'category_copying', target, source_file=str(source), target_file=str(target))
                        row['copied'] = self.copy_checked(source, target, item['sha256'], item['size_bytes'], reserve)
                        if row['copied'] and str(target) not in record['created_files']:
                            record['created_files'].append(str(target))
                        item['locations'] = [loc for loc in item['locations'] if loc['role'] != 'managed']
                        item['locations'].append({'role': 'managed', 'protocol': 'file', 'path': str(target), 'uri': target.as_uri(), 'status': 'available', 'verified_at': now()})
                        item['revision'] += 1
                        row['after'] = item
                        record['processed'] += 1
                        self.journal(record, {'row_index': row_index, 'row': row, 'created': str(target) if row['copied'] else None})
                    if stopped():
                        record['status'] = 'stopped'
                        self.save(record)
                        return record
                    # Keep originals accessible until every new copy is verified.
                    replacements = {row['after']['media_id']: row['after'] for row in record['rows']}
                    record['stage'] = 'db_committing'
                    self.save(record)
                    self.library.commit([replacements.get(item['media_id'], item) for item in items])
                # A resumed post-commit run must not retire the old location if
                # its replacement has disappeared or changed since the copy.
                for row in record['rows']:
                    self.verify(self.checked(row['destination'], root), row['before']['sha256'], row['before']['size_bytes'])
                record.update(status='running', stage='archiving')
                self.save(record)
                protected = self.protected_paths(self.library.items())
                moves = {move['original']: move for move in record['moves']}
                for row in record['rows']:
                    for loc in row['before']['locations']:
                        if loc['role'] != 'managed':
                            continue
                        path = self.checked(loc['path'], root)
                        if str(path) in protected or path.is_relative_to(root / '.trash'):
                            continue
                        if str(path) not in moves and path.exists():
                            # Stale additional copies can differ from the current
                            # media: record their actual bytes for faithful undo.
                            moves[str(path)] = {'original': str(path), 'saved': str(root / '.trash' / 'category-merges' / record['operation_id'] / path.relative_to(root)),
                                                'sha256': digest(path), 'size_bytes': path.stat().st_size}
                record['moves'] = list(moves.values())
                self.save(record)
                for move in record['moves']:
                    if stopped():
                        record['status'] = 'stopped'
                        self.save(record)
                        return record
                    original, saved = self.checked(move['original'], root), self.checked(move['saved'], root)
                    if str(original) in protected:
                        continue
                    self.emit(record, progress, 'category_archiving', original, 'managed_file', target_file=str(saved))
                    self.move_checked(original, saved, move['sha256'], move['size_bytes'])
                    move['moved'] = True
                    self.journal(record, {'move': move})
                record.update(status='completed', stage='completed', finished_at=now())
                record.pop('error', None)
                self.save(record)
                return record
            except Exception as exc:
                record.update(status='recovery_required', error=str(exc))
                self.save(record)
                raise

    def undo(self, operation_id, progress=None):
        progress = progress or (lambda state: None)
        with self.library.writing():
            record = self.load(operation_id)
            if record['status'] == 'undone':
                return record
            root = self.root(record)
            items = self.library.items()
            state = self.database_state(record, items)
            reserve = self.library.config().get('scan_min_free_mb', 512) * 1048576
            try:
                record.update(status='running', stage='undo_restoring')
                self.save(record)
                # Restore old files first; DB still points at verified new paths.
                for move in record['moves']:
                    original, saved = self.checked(move['original'], root), self.checked(move['saved'], root)
                    self.emit(record, progress, 'category_restoring', saved, 'managed_file', target_file=str(original))
                    if original.exists():
                        self.verify(original, move['sha256'], move['size_bytes'])
                    else:
                        self.move_checked(saved, original, move['sha256'], move['size_bytes'])
                for row in record['rows']:
                    # A pre-commit stopped run has no archived originals.
                    source = self.checked(row['source'], root)
                    self.verify(source, row['before']['sha256'], row['before']['size_bytes'])
                if state == 'after':
                    replacements = {row['before']['media_id']: row['before'] for row in record['rows']}
                    record['stage'] = 'undo_db_committing'
                    self.save(record)
                    self.library.commit([replacements.get(item['media_id'], item) for item in items])
                record['stage'] = 'undo_archiving'
                self.save(record)
                protected = self.protected_paths(self.library.items())
                by_target = {row['destination']: row for row in record['rows']}
                for value in record['created_files']:
                    if value in protected or value not in by_target:
                        continue
                    target = self.checked(value, root)
                    if target.exists():
                        item = by_target[value]['before']
                        saved = self.checked(str(root / '.trash' / 'category-merges' / record['operation_id'] / 'undo' / target.relative_to(root)), root)
                        self.emit(record, progress, 'category_archiving', target, 'managed_file', target_file=str(saved))
                        self.move_checked(target, saved, item['sha256'], item['size_bytes'])
                record.update(status='undone', stage='undone', undone_at=now())
                record.pop('error', None)
                self.save(record)
                return record
            except Exception as exc:
                record.update(status='recovery_required', error=str(exc))
                self.save(record)
                raise
