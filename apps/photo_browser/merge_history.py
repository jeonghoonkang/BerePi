"""Persistent JSON and standalone HTML reports for each merge invocation."""
import html
import os
import shutil
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from library import atomic_json, component, now, read_json, uid


def directory_snapshot(root, progress=None):
    """Logical file bytes, not allocated blocks; exclude trash, links and staging."""
    started = now()
    files, directories, errors, links = {}, {'.': {'direct_files': 0, 'direct_bytes': 0}}, [], []
    if root.exists():
        def failed(exc):
            errors.append(str(exc))
        for base, children, names in os.walk(root, followlinks=False, onerror=failed):
            folder = Path(base)
            kept = []
            for name in sorted(children):
                child = folder / name
                if name == '.trash':
                    continue
                if child.is_symlink():
                    links.append(child.relative_to(root).as_posix())
                    continue
                kept.append(name)
                directories[child.relative_to(root).as_posix()] = {'direct_files': 0, 'direct_bytes': 0}
            children[:] = kept
            key = folder.relative_to(root).as_posix()
            for name in sorted(names):
                path = folder / name
                relative = path.relative_to(root).as_posix()
                if path.is_symlink():
                    links.append(relative)
                    continue
                if name.startswith('.') and name.endswith('.part'):
                    continue
                try:
                    if not path.is_file():
                        continue
                    stat = path.stat()
                    files[relative] = {'size_bytes': stat.st_size, 'mtime_ns': stat.st_mtime_ns}
                    directories[key]['direct_files'] += 1
                    directories[key]['direct_bytes'] += stat.st_size
                except OSError as exc:
                    errors.append(f'{relative}: {exc}')
            if progress:
                progress({'phase': 'report_inventory', 'inventory_complete': False, 'processed': 0,
                          'report_files': len(files), 'current_file': str(folder)})
    for entry in directories.values():
        entry.update(file_count=entry['direct_files'], total_bytes=entry['direct_bytes'])
    for key in sorted(directories, key=lambda value: len(Path(value).parts), reverse=True):
        if key != '.':
            parent = Path(key).parent.as_posix()
            directories[parent]['file_count'] += directories[key]['file_count']
            directories[parent]['total_bytes'] += directories[key]['total_bytes']
    existing = root
    while not existing.exists():
        existing = existing.parent
    try:
        disk = shutil.disk_usage(existing)
        volume = {'total_bytes': getattr(disk, 'total', None), 'used_bytes': getattr(disk, 'used', None), 'free_bytes': disk.free}
    except OSError as exc:
        volume = None
        errors.append(str(exc))
    return {'root': str(root), 'exists': root.exists(), 'started_at': started, 'finished_at': now(),
            'file_count': len(files), 'directory_count': len(directories) - 1,
            'total_bytes': sum(value['size_bytes'] for value in files.values()),
            'directories': [{'path': key, **value} for key, value in sorted(directories.items())],
            'files': files, 'volume': volume, 'complete': not errors, 'errors': errors, 'excluded_symlinks': links,
            'exclusions': ['.trash directories', 'symlinks', 'hidden *.part staging files']}


def atomic_text(path, text):
    temporary = path.with_name(path.name + '.' + uid() + '.tmp')
    try:
        with temporary.open('w', encoding='utf-8') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def table(headers, rows):
    escape = lambda value: html.escape(str(value), quote=True)
    return '<table><thead><tr>' + ''.join('<th>' + escape(h) + '</th>' for h in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + escape(v) + '</td>' for v in row) + '</tr>' for row in rows) + '</tbody></table>'


def render_html(report):
    escape = lambda value: html.escape(str(value), quote=True)
    def local_time(value):
        return datetime.fromisoformat(value).astimezone(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S KST') if value else '진행 중'
    summary, before, after = report['summary'], report['before'], report.get('after')
    parts = ['<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BerePi 병합 보고서</title><style>body{font:15px system-ui;max-width:1400px;margin:32px auto;padding:0 20px;color:#172333}table{border-collapse:collapse;width:100%;margin:16px 0;font-size:13px}td,th{border:1px solid #ccd4dd;padding:8px;text-align:left;overflow-wrap:anywhere}th{background:#edf3f8}p{overflow-wrap:anywhere}.scroll{overflow:auto}h2{margin-top:32px}</style><body><h1>BerePi 병합 실행 보고서</h1>']
    parts.append(table(['항목', '값'], [
        ('보고서 ID', report['report_id']), ('병합 ID', report['merge_id']), ('상태', report['status']),
        ('시작 시간', local_time(report['started_at'])), ('종료 시간', local_time(report.get('finished_at'))),
        ('소요 시간(초)', report.get('duration_seconds', '진행 중')), ('이어하기 실행', report['resumed']),
        ('관리 디렉토리', report['managed_root']), ('DB 디렉토리', report['db']),
        ('이번 실행 처리 / 실행 대상', f"{summary['processed_count']} / {summary['target_count']}"),
        ('새 복사 / 동일 내용 재사용', f"{summary['copied_count']} / {summary['reused_count']}"),
        ('이번 대상 내 동일 SHA-256 중복 항목', summary['identical_content_duplicate_count']),
        ('이름 충돌로 새 이름에 복사', summary['renamed_copied_count']),
        ('이름 구분 경로 재사용', summary['renamed_reused_count']),
        ('오류 / 건너뜀', f"{summary['error_count']} / {summary['skipped_count']}"),
        ('이전 실행까지 처리한 항목', summary['previous_processed_count'])]))
    parts.append('<h2>소스 · 분류 · 소유자 · 원본 위치</h2>')
    parts.append(table(['소스 ID', '카테고리', '소유자 ID', '프로토콜 / 호스트', '원본 루트', '대상 수', '새 복사', '재사용', '이름 변경 복사', '오류'],
        [(s['source_id'], s['category_id'], s['owner_id'], s['protocol'] + ' / ' + str(s['host'] or ''), s['root'], s['target_count'], s['copied_count'], s['reused_count'], s['renamed_copied_count'], s['error_count']) for s in report['sources']]))
    parts.append('<h2>관리 디렉토리 전후 비교</h2><p>용량은 파일 논리 크기 합계(바이트)입니다. 휴지통·심볼릭 링크·복사 임시 파일은 제외합니다. 외부 프로그램의 변경도 전후 차이에 포함될 수 있습니다.</p>')
    parts.append(table(['구분', '파일 수', '하위 디렉토리 수', '파일 용량(bytes)', '볼륨 여유(bytes)', '조회 완전성'],
        [(name, snapshot['file_count'], snapshot['directory_count'], snapshot['total_bytes'], (snapshot.get('volume') or {}).get('free_bytes', ''), snapshot['complete']) for name, snapshot in [('병합 전', before), ('병합 후', after)] if snapshot]))
    if report.get('delta'):
        delta = report['delta']
        parts.append(table(['추가 파일', '제거 파일', '크기·수정시각 변경 파일', '파일 수 증감', '용량 증감(bytes)'], [(delta['added_count'], delta['removed_count'], delta['modified_count'], delta['file_count_change'], delta['total_bytes_change'])]))
    for name, snapshot in [('병합 전 디렉토리 구성', before), ('병합 후 디렉토리 구성', after)]:
        if not snapshot:
            continue
        parts.append('<h2>' + name + '</h2>')
        parts.append(table(['상대 경로', '직접 파일 수', '직접 용량(bytes)', '하위 포함 파일 수', '하위 포함 용량(bytes)'], [(d['path'], d['direct_files'], d['direct_bytes'], d['file_count'], d['total_bytes']) for d in snapshot['directories']]))
        if snapshot['errors']:
            parts.append('<p>조회 오류: ' + escape(' / '.join(snapshot['errors'])) + '</p>')
    parts.append('<h2>이름만 중복되어 새 이름으로 복사한 파일</h2>')
    parts.append(table(['미디어 ID', '원본 위치', '변경 전 예정 경로', '새 저장 경로', '용량(bytes)'], [(o['media_id'], ' / '.join(l.get('path') or l.get('uri', '') for l in o['source_locations']), o.get('original_destination', ''), o.get('destination', ''), o['size_bytes']) for o in report['renamed_files']]))
    parts.append('<h2>이번 실행 처리 내역 (오류·재사용 포함)</h2>')
    parts.append(table(['원본 이름', '소스 ID', '원본 위치', '저장 위치', '상태', '오류'], [(o['name'], ', '.join(l.get('source_id', '') for l in o['source_locations']), ' / '.join(l.get('path') or l.get('uri', '') for l in o['source_locations']), o.get('destination', ''), o['status'], o.get('error', '')) for o in report['operations']]))
    parts.append('<h2>실제로 추가된 파일</h2>')
    parts.append(table(['관리 디렉토리 상대 경로', '용량(bytes)'], [(f['path'], f['size_bytes']) for f in report.get('delta', {}).get('added_files', [])]))
    if report.get('warning'):
        parts.append('<p>' + escape(report['warning']) + '</p>')
    parts.append('</body></html>')
    return ''.join(parts)


class MergeHistory:
    def __init__(self, library, root, resume, progress):
        self.library, self.root, self.progress = library, root, progress
        self.clock = time.monotonic()
        self.report_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_') + uid()
        self.merge_id = component(resume) if resume else uid()
        self.directory = library.db / 'reports' / 'merges'
        self.operations, self.items, self.previous_count, self.wanted = [], {}, 0, set()
        self.data = {'schema_version': 1, 'report_id': self.report_id, 'merge_id': self.merge_id,
                     'started_at': now(), 'finished_at': None, 'duration_seconds': None, 'status': 'running',
                     'resumed': bool(resume), 'managed_root': str(root), 'db': str(library.db),
                     'source_settings': library.config()['sources'], 'sources': [], 'operations': [], 'renamed_files': []}
        self.data['before'] = directory_snapshot(root, progress)

    def bind(self, state, items):
        self.operations = state['operations']
        self.previous_count = len(self.operations)
        self.items = {i['media_id']: i for i in items}
        self.wanted = set(state['ids']) - {o['media_id'] for o in self.operations}
        self.data['merge_started_at'] = state.get('merge_started_at', self.data['started_at'])
        self.save()

    def summarize(self):
        operations = []
        for op in self.operations[self.previous_count:]:
            item = self.items.get(op['media_id'], {})
            operations.append({**op, 'name': item.get('name', ''), 'size_bytes': item.get('size_bytes', 0),
                               'source_locations': op.get('source_locations', [dict(l) for l in item.get('locations', []) if l['role'] == 'source'])})
        counts = Counter(op['status'] for op in operations)
        selected = [i for mid, i in self.items.items() if mid in self.wanted]
        summary = {'target_count': len(self.wanted), 'session_target_count': len(self.wanted) + self.previous_count,
                   'previous_processed_count': self.previous_count, 'processed_count': len(operations),
                   'copied_count': counts['copied'], 'reused_count': counts['reused'],
                   'error_count': counts['error'], 'skipped_count': counts['skipped'],
                   'renamed_copied_count': sum(o.get('renamed', False) and o['status'] == 'copied' for o in operations),
                   'renamed_reused_count': sum(o.get('renamed', False) and o['status'] == 'reused' for o in operations),
                   'copied_bytes': sum(o['size_bytes'] for o in operations if o['status'] == 'copied'),
                   'identical_content_duplicate_count': sum(count - 1 for count in Counter(i['sha256'] for i in selected).values())}
        groups = {}
        source_settings = {s['source_id']: s for s in self.data['source_settings']}
        by_media = {o['media_id']: o for o in operations}
        for item in selected:
            c = item['classification']
            for location in (l for l in item['locations'] if l['role'] == 'source'):
                sid = location.get('source_id', '')
                key = sid, c['category_id'], c['owner_id']
                if key not in groups:
                    groups[key] = {'source_id': sid, 'category_id': c['category_id'], 'owner_id': c['owner_id'],
                                   'protocol': location['protocol'], 'host': location.get('host'),
                                   'root': source_settings.get(sid, {}).get('root', ''), 'target_count': 0,
                                   'copied_count': 0, 'reused_count': 0, 'renamed_copied_count': 0, 'error_count': 0}
                group = groups[key]
                group['target_count'] += 1
                op = by_media.get(item['media_id'], {})
                for outcome in ('copied', 'reused', 'error'):
                    group[outcome + '_count'] += op.get('status') == outcome
                group['renamed_copied_count'] += op.get('status') == 'copied' and op.get('renamed', False)
        self.data.update(summary=summary, operations=operations, sources=list(groups.values()),
                         renamed_files=[o for o in operations if o.get('renamed') and o['status'] == 'copied'])

    def save(self):
        self.summarize()
        atomic_json(self.directory / (self.report_id + '.json'), self.data)
        atomic_text(self.directory / (self.report_id + '.html'), render_html(self.data))
        metadata = {key: self.data[key] for key in ('report_id', 'merge_id', 'started_at', 'finished_at', 'duration_seconds', 'status', 'resumed', 'summary', 'managed_root')}
        metadata['files'] = {format: str(self.directory / (self.report_id + '.' + format)) for format in ('json', 'html')}
        metadata['before'] = {k: self.data['before'][k] for k in ('file_count', 'directory_count', 'total_bytes', 'complete')}
        if self.data.get('after'):
            metadata['after'] = {k: self.data['after'][k] for k in ('file_count', 'directory_count', 'total_bytes', 'complete')}
        atomic_json(self.directory / (self.report_id + '.summary.json'), metadata)
        return metadata

    def finish(self, result):
        self.data['after'] = directory_snapshot(self.root, self.progress)
        before, after = self.data['before'], self.data['after']
        added = after['files'].keys() - before['files'].keys()
        removed = before['files'].keys() - after['files'].keys()
        modified = [key for key in before['files'].keys() & after['files'].keys() if before['files'][key] != after['files'][key]]
        self.data['delta'] = {'added_count': len(added), 'removed_count': len(removed), 'modified_count': len(modified),
                              'file_count_change': after['file_count'] - before['file_count'], 'total_bytes_change': after['total_bytes'] - before['total_bytes'],
                              'complete': before['complete'] and after['complete'],
                              'added_files': [{'path': key, **after['files'][key]} for key in sorted(added)],
                              'removed_files': sorted(removed), 'modified_files': sorted(modified)}
        self.data.update(status=result['status'], finished_at=now(), duration_seconds=round(time.monotonic() - self.clock, 3),
                         warning=result.get('warning'), disk_space=result.get('disk_space'))
        return self.save()


def list_reports(library):
    reports = []
    for path in (library.db / 'reports' / 'merges').glob('*.summary.json'):
        try:
            report = read_json(path)
            if isinstance(report, dict) and report.get('report_id') and report.get('started_at'):
                reports.append(report)
        except (OSError, ValueError):
            continue
    return sorted(reports, key=lambda r: r['started_at'], reverse=True)


def first_merge_start(library, merge_id, fallback):
    """Recover the earliest timestamp for legacy checkpoints as well as new ones."""
    values = []
    checkpoint = read_json(library.db / 'merges' / (component(merge_id) + '.json'), {})
    if checkpoint.get('merge_started_at'):
        return checkpoint['merge_started_at']
    for directory, pattern in [('jobs', '*.json'), ('reports/merges', '*.summary.json')]:
        for path in (library.db / directory).glob(pattern):
            try:
                value = read_json(path)
                detail = value.get('result') or value.get('progress') or {}
                if value.get('merge_id') == merge_id or detail.get('merge_id') == merge_id:
                    stamp = value.get('started_at') or value.get('created_at')
                    if stamp:
                        values.append(stamp)
            except (ValueError, OSError, AttributeError):
                continue
    return min(values, key=lambda value: datetime.fromisoformat(value)) if values else fallback
