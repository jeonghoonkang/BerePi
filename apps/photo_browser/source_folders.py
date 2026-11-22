"""Stable, directory-named sources and explicit incremental scan/copy batches."""
import hashlib
from pathlib import Path
import re
import unicodedata

from library import component


def normalize_roots(value):
    if not isinstance(value, list) or len(value) > 100:
        raise ValueError('소스 기준 디렉토리는 최대 100개 목록이어야 합니다.')
    result = []
    for entry in value:
        if not isinstance(entry, dict) or not isinstance(entry.get('root'), str) or not entry['root'].strip():
            raise ValueError('소스 기준 디렉토리 경로가 필요합니다.')
        result.append({'root': entry['root'], 'category': component(entry.get('category', 'family')),
                       'owner_id': component(entry.get('owner_id', 'default'))})
    return result


class SourceFolders:
    def __init__(self, library):
        self.library = library

    def directory(self, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError('소스 기준 디렉토리를 입력하세요.')
        path = self.library.local(value.strip())
        if not path.is_dir():
            raise ValueError('소스 기준 디렉토리가 없거나 폴더가 아닙니다.')
        config = self.library.config()
        if any(path.is_relative_to(other) for other in (self.library.db, Path(config['managed_root']).resolve())):
            raise ValueError('DB 또는 관리 디렉토리를 소스로 지정할 수 없습니다.')
        return path

    @staticmethod
    def source_id(path, used):
        stem = re.sub(r'[^\w-]+', '_', unicodedata.normalize('NFKC', path.name)).strip('_-') or 'folder'
        stem = stem[:80]
        try:
            component(stem)
        except ValueError:
            stem = 'folder_' + stem[:73]
        if stem not in used:
            return stem
        base = stem[:63] + '_' + hashlib.sha256(str(path).encode()).hexdigest()[:12]
        candidate, suffix = base, 2
        while candidate in used:
            candidate = base + '_' + str(suffix)
            suffix += 1
        return component(candidate)

    def register(self, root, category='family', owner_id='default'):
        root = self.directory(root)
        category, owner_id = component(category), component(owner_id)
        with self.library.lock:
            config = self.library.config()
            managed = Path(config['managed_root']).resolve()
            existing = {self.library.source_key(source): source for source in config['sources']}
            used = {source['source_id'] for source in config['sources']}
            reports, skipped = [], []
            for child in sorted(root.iterdir(), key=lambda path: (path.name.casefold(), path.name)):
                if child.is_symlink() or child.name.startswith('.'):
                    skipped.append({'name': child.name, 'reason': '링크 또는 숨김 항목'})
                    continue
                if not child.is_dir():
                    continue
                child = self.library.local(str(child))
                if any(child.is_relative_to(other) or other.is_relative_to(child)
                       for other in (self.library.db, managed)):
                    skipped.append({'name': child.name, 'reason': 'DB·관리 디렉토리와 경로 중첩'})
                    continue
                source = existing.get(('file', str(child)))
                added = source is None
                if added:
                    source = {'source_id': self.source_id(child, used), 'protocol': 'file', 'root': str(child),
                              'category': category, 'owner_id': owner_id, 'recursive': True}
                    used.add(source['source_id'])
                    config['sources'].append(source)
                    existing[('file', str(child))] = source
                reports.append({'source': source, 'added': added})
            roots = normalize_roots(config.get('source_folder_roots', []))
            roots = [entry for entry in roots if entry['root'] != str(root)]
            roots.append({'root': str(root), 'category': category, 'owner_id': owner_id})
            config['source_folder_roots'] = normalize_roots(roots)
            self.library.save_config(config)
        return {'root': str(root), 'items': reports, 'skipped': skipped,
                'added': sum(report['added'] for report in reports)}

    def sync(self, root, progress, stopped):
        root = self.directory(root)
        setting = next((entry for entry in self.library.config().get('source_folder_roots', [])
                        if entry['root'] == str(root)), None)
        if setting is None:
            raise ValueError('먼저 기준 디렉토리를 저장하고 하위 폴더를 등록하세요.')
        if stopped():
            return {'status': 'stopped', 'items': []}
        registration = self.register(str(root), setting['category'], setting['owner_id'])
        results = []
        def result(status):
            return {'status': status, 'root': str(root), 'registration': registration, 'items': results,
                    'error_count': sum(bool(item.get('error')) for item in results)}
        for report in registration['items']:
            if stopped():
                return result('stopped')
            source_id = report['source']['source_id']
            current = {'source_id': source_id}
            results.append(current)
            def update(state):
                progress({**state, 'folder_source_id': source_id, 'folder_processed': len(results) - 1,
                          'folder_total': len(registration['items'])})
            try:
                scan = self.library.scan(source_id, mode='incremental', progress=update, stopped=stopped)
                current['scan'] = {key: scan.get(key) for key in ('status', 'published', 'processed', 'total')}
                if scan['status'] == 'paused_low_space':
                    current['error'] = scan.get('warning', '스캔 저장 공간이 부족합니다.')
                    return result('paused_low_space')
                if stopped() or scan['status'] == 'stopped':
                    return result('stopped')
                if scan['status'] != 'completed' or not scan.get('published') or scan.get('errors'):
                    current['error'] = '스캔이 오류 없이 완료되지 않아 해당 소스는 복사하지 않았습니다.'
                    continue
                if not scan.get('total'):
                    current['merge'] = {'status': 'skipped_empty', 'processed': 0, 'total': 0}
                    continue
                merged = self.library.merge(source_id=source_id, progress=update, stopped=stopped)
                current['merge'] = {key: merged.get(key) for key in ('status', 'merge_id', 'processed', 'total')}
                if merged['status'] != 'completed' or any(op['status'] == 'error' for op in merged.get('operations', [])):
                    current['error'] = '병합이 완료되지 않았습니다. 작업 내역을 확인하세요.'
                if merged['status'] in {'blocked_low_space', 'paused_low_space'}:
                    current['error'] = merged.get('warning', '병합 저장 공간이 부족합니다.')
                    return result(merged['status'])
                if stopped() or merged['status'] == 'stopped':
                    return result('stopped')
            except (ValueError, OSError, KeyError) as exc:
                current['error'] = str(exc)
        return result('failed' if any(item.get('error') for item in results) else 'completed')
