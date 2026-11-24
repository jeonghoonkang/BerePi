"""Read-only, bounded-memory DB accounting and bounded JSON inspection."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import heapq
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time


CLASSES = {
    'current_media': '현재 사용 미디어 JSON', 'unreferenced_media': '미참조 미디어 JSON (과거 세대 후보)',
    'unknown_media': '인덱스 확인 불가 미디어 파일', 'current_duplicates': '현재 참조 중복 정보',
    'media_aux': '미디어 폴더의 임시·기타 파일',
    'old_duplicates': '기타·과거 중복 정보', 'scans': '스캔 상태·목록·저널',
    'merges': '병합 체크포인트·보고서', 'recovery': '카테고리 통합·DB 정리·복구 기록',
    'cache': '원격 미디어 캐시', 'downloads': '다운로드 ZIP·임시 파일',
    'ai': 'AI 요청·분석 결과', 'monitoring': '경로 점검·사용량 캐시·이력',
    'metadata': '설정·인덱스·인증·잠금', 'other': '기타 파일'}


def human_bytes(value):
    amount = float(value)
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB'):
        if amount < 1024 or unit == 'PiB':
            return f'{amount:,.2f} {unit}'
        amount /= 1024


def link(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)


class DBAudit:
    def __init__(self, db, max_json_bytes=32 * 1024 * 1024):
        self.db = Path(db).expanduser().resolve()
        if not self.db.is_dir():
            raise ValueError(f'DB 디렉토리가 없습니다: {self.db}')
        self.max_json_bytes = max_json_bytes
        self.errors = []
        self.error_count = 0
        self.current = set()
        self.duplicates = set()
        self.manifest = None
        self.index_fingerprint = None
        try:
            data = self.read_bytes('index.json')
            value = json.loads(data)
            if not isinstance(value, dict) or not isinstance(value.get('chunks'), list):
                raise ValueError('index.json의 chunks가 올바르지 않습니다.')
            self.current = {self.reference(chunk['path']) for chunk in value['chunks']}
            if value.get('duplicates'):
                self.duplicates.add(self.reference(value['duplicates']))
            self.manifest = value
            self.index_fingerprint = hashlib.sha256(data).hexdigest()
        except (OSError, ValueError, TypeError, KeyError) as exc:
            self.problem('index.json', exc)

    def problem(self, path, error):
        self.error_count += 1
        if len(self.errors) < 20:
            self.errors.append({'path': str(path), 'error': str(error)})

    @staticmethod
    def reference(value):
        if not isinstance(value, str):
            raise ValueError('DB 내부의 상대 경로가 필요합니다.')
        path = PurePosixPath(value.replace('\\', '/'))
        if path.is_absolute() or not path.parts or any(part in {'..', '.'} or ':' in part for part in path.parts):
            raise ValueError('DB 내부의 상대 경로만 허용합니다.')
        return path.as_posix()

    def safe_file(self, relative):
        relative = self.reference(relative)
        path = self.db
        for part in PurePosixPath(relative).parts:
            path = path / part
            if link(path.lstat()):
                raise ValueError('심볼릭 링크·정션은 읽지 않습니다.')
        if not stat.S_ISREG(path.lstat().st_mode):
            raise ValueError('일반 파일이 아닙니다.')
        return path

    def read_bytes(self, relative, limit=None):
        with self.safe_file(relative).open('rb') as stream:
            data = stream.read((limit or self.max_json_bytes) + 1)
        if len(data) > (limit or self.max_json_bytes):
            raise ValueError('JSON 읽기 한도를 초과했습니다. --max-json-mib 또는 --max-bytes를 늘려 주세요.')
        return data

    def classify(self, relative):
        if relative in self.current and self.manifest is not None:
            return 'current_media'
        if relative in self.duplicates and self.manifest is not None:
            return 'current_duplicates'
        head = relative.split('/')[0]
        if head == 'media':
            if not relative.lower().endswith('.json'): return 'media_aux'
            return 'unreferenced_media' if self.manifest is not None else 'unknown_media'
        if head == 'duplicates': return 'metadata' if relative == 'duplicates/latest.json' else 'old_duplicates'
        if head == 'scans': return 'scans'
        if head in {'merges', 'merge-progress'} or relative.startswith('reports/merges/'): return 'merges'
        if head in {'category_merges', 'duplicate_cleanups', 'source_cleanup', 'trash'}: return 'recovery'
        if head in {'cache', 'downloads', 'ai'}: return head
        if head in {'source-path-health', 'storage-usage', 'pair-history', 'source_comparisons'}: return 'monitoring'
        return 'metadata' if '/' not in relative else 'other'

    def contents(self, progress=None):
        summary = {'expected_chunks': len(self.current), 'read_chunks': 0, 'records': 0,
                   'active_items': 0, 'inactive_items': 0, 'media_types': Counter(),
                   'lifecycle': Counter(), 'categories': Counter(), 'sources': Counter()}
        ids = set()
        for number, relative in enumerate(sorted(self.current)):
            try:
                page = json.loads(self.read_bytes(relative))
                if not isinstance(page, dict) or not isinstance(page.get('items'), list):
                    raise ValueError('미디어 청크의 items가 올바르지 않습니다.')
                for item in page['items']:
                    status = item['lifecycle']['status']
                    category = item['classification']['category_id']
                    summary['records'] += 1
                    ids.add(item['media_id'])
                    summary['lifecycle'][status] += 1
                    summary['media_types'][item.get('media_type', 'unknown')] += 1
                    if status == 'active':
                        summary['active_items'] += 1
                        summary['categories'][category] += 1
                        for source in {loc.get('source_id') for loc in item['locations'] if loc['role'] == 'source' and loc.get('source_id')}:
                            summary['sources'][source] += 1
                    else:
                        summary['inactive_items'] += 1
                summary['read_chunks'] += 1
            except (OSError, ValueError, TypeError, KeyError) as exc:
                self.problem(relative, exc)
            if progress: progress('contents', number + 1, len(self.current))
        summary['unique_media_ids'] = len(ids)
        summary['duplicate_media_id_records'] = summary['records'] - len(ids)
        return summary

    def scan(self, top=20, with_contents=True, max_files=None, progress=None):
        started = time.monotonic()
        totals = {'file_count': 0, 'json_count': 0, 'jsonl_count': 0, 'logical_bytes': 0, 'allocated_bytes': 0}
        classes, largest = defaultdict(lambda: {key: 0 for key in totals}), []
        complete, interrupted, skipped_links, estimated = True, False, 0, False
        seen_current = set()
        content_summary = None
        folders = [(self.db, '')]
        try:
            if with_contents and self.manifest is not None:
                content_summary = self.contents(progress)
            while folders:
                folder, prefix = folders.pop()
                try:
                    with os.scandir(folder) as entries:
                        for entry in entries:
                            relative = prefix + entry.name
                            try:
                                info = entry.stat(follow_symlinks=False)
                                if link(info):
                                    skipped_links += 1
                                    continue
                                if stat.S_ISDIR(info.st_mode):
                                    folders.append((Path(entry.path), relative + '/'))
                                    continue
                                if not stat.S_ISREG(info.st_mode):
                                    continue
                                kind = self.classify(relative)
                                if relative in self.current: seen_current.add(relative)
                                suffix = Path(entry.name).suffix.lower()
                                blocks = getattr(info, 'st_blocks', None)
                                estimated |= blocks is None
                                counts = {'file_count': 1, 'json_count': int(suffix == '.json'), 'jsonl_count': int(suffix == '.jsonl'),
                                          'logical_bytes': info.st_size, 'allocated_bytes': info.st_size if blocks is None else blocks * 512}
                                for key, value in counts.items():
                                    totals[key] += value
                                    classes[kind][key] += value
                                if top:
                                    candidate = (info.st_size, relative, kind)
                                    if len(largest) < top: heapq.heappush(largest, candidate)
                                    elif candidate > largest[0]: heapq.heapreplace(largest, candidate)
                                if progress: progress('files', totals['file_count'], totals['logical_bytes'])
                                if max_files is not None and totals['file_count'] >= max_files:
                                    complete = False
                                    folders.clear()
                                    break
                            except (OSError, ValueError) as exc:
                                self.problem(relative, exc)
                except OSError as exc:
                    self.problem(folder, exc)
        except KeyboardInterrupt:
            complete, interrupted = False, True
        changed = None
        if self.index_fingerprint is not None:
            try: changed = hashlib.sha256(self.read_bytes('index.json')).hexdigest() != self.index_fingerprint
            except (OSError, ValueError) as exc:
                self.problem('index.json', exc)
                changed = True
        rows = [{'class': kind, 'label': CLASSES[kind], **counts,
                 'percent': round(counts['logical_bytes'] * 100 / totals['logical_bytes'], 2) if totals['logical_bytes'] else 0}
                for kind, counts in classes.items()]
        missing = self.current - seen_current if complete and self.manifest is not None else None
        return {'db': str(self.db), 'observed_at': datetime.now(timezone.utc).isoformat(),
                'complete': complete and self.error_count == 0 and not changed and not missing, 'walk_complete': complete,
                'interrupted': interrupted, 'index_changed_during_audit': changed, 'index_valid': self.manifest is not None,
                'elapsed_seconds': round(time.monotonic() - started, 2), 'totals': totals,
                'allocation_estimated': estimated, 'skipped_links': skipped_links, 'error_count': self.error_count, 'errors': self.errors,
                'missing_current_chunk_count': len(missing) if missing is not None else None,
                'missing_current_chunk_samples': sorted(missing)[:20] if missing else [],
                'classes': sorted(rows, key=lambda row: row['logical_bytes'], reverse=True), 'contents': content_summary,
                'largest_files': [{'path': path, 'class': kind, 'size_bytes': size} for size, path, kind in sorted(largest, reverse=True)],
                'note': '읽기 전용 집계입니다. 용량·파일 수는 경로별 합계로 하드링크는 중복 계산될 수 있습니다. 할당량은 st_blocks 지원 시 사용하며 미지원 환경에서는 논리 용량으로 추정합니다. 미참조 파일은 삭제 가능 판정이 아닙니다. 실행 중 DB가 변경되면 다시 집계하세요.'}


def table(report):
    total = report['totals']
    lines = [f"DB: {report['db']}", f"집계: {'완료' if report['complete'] else '부분 집계 / 확인 필요'} · {report['elapsed_seconds']}초",
             f"집계 파일 {total['file_count']:,}개 · JSON {total['json_count']:,}개 · JSONL {total['jsonl_count']:,}개",
             f"논리 용량 {human_bytes(total['logical_bytes'])} · 할당량(경로 합계) {human_bytes(total['allocated_bytes'])}",
             f"링크·정션 제외 {report['skipped_links']:,}개 · 할당량 {'논리 용량으로 추정' if report['allocation_estimated'] else '파일 블록 기준'}",
             '', '분류 | 파일 수 | JSON 수 | 논리 용량 | 할당량(경로 합) | 비율']
    for row in report['classes']:
        lines.append(f"{row['label']} | {row['file_count']:,} | {row['json_count']:,} | {human_bytes(row['logical_bytes'])} | {human_bytes(row['allocated_bytes'])} | {row['percent']:.2f}%")
    if report['contents']:
        content = report['contents']
        lines += ['', f"현재 청크 {content['read_chunks']:,}/{content['expected_chunks']:,}개 · DB 항목 {content['records']:,}개 · 고유 ID {content['unique_media_ids']:,}개",
                  f"활성 {content['active_items']:,}개 · 비활성 {content['inactive_items']:,}개",
                  f"전체 DB 기록 형식: 사진 {content['media_types'].get('image', 0):,}개 · 동영상 {content['media_types'].get('video', 0):,}개",
                  '활성 카테고리: ' + json.dumps(content['categories'], ensure_ascii=False),
                  '활성 소스: ' + json.dumps(content['sources'], ensure_ascii=False)]
    lines += ['', '용량이 큰 파일:']
    lines += [f"{human_bytes(row['size_bytes'])} | {CLASSES[row['class']]} | {row['path']}" for row in report['largest_files']]
    if report['index_changed_during_audit']: lines.append('주의: 집계 중 index.json이 변경되었습니다. 현재·과거 분류는 시작 시점 기준입니다.')
    if report['missing_current_chunk_count']: lines.append(f"주의: 현재 인덱스 참조 청크 {report['missing_current_chunk_count']:,}개를 일반 파일로 확인하지 못했습니다.")
    if report['error_count']: lines.append(f"오류 {report['error_count']:,}건: " + json.dumps(report['errors'], ensure_ascii=False))
    lines.append(report['note'])
    return '\n'.join(lines)


def inspect_json(db, relative, limit=3, max_bytes=1024 * 1024):
    audit = DBAudit(db)
    path = audit.safe_file(relative)
    if path.suffix.lower() not in {'.json', '.jsonl'}:
        raise ValueError('JSON 또는 JSONL 파일만 조회할 수 있습니다.')
    if path.suffix.lower() == '.jsonl':
        values, remaining = [], max_bytes
        with path.open('rb') as stream:
            for _ in range(limit):
                line = stream.readline(remaining + 1)
                if not line: break
                remaining -= len(line)
                if remaining < 0: raise ValueError('JSONL 읽기 한도를 초과했습니다. --max-bytes를 늘려 주세요.')
                values.append(json.loads(line))
            more = bool(stream.read(1))
        value = values
    else:
        value = json.loads(audit.read_bytes(relative, max_bytes))
        more = False
    truncated = []
    def preview(value, field='$'):
        if isinstance(value, dict):
            return {key: '[REDACTED]' if re.search(r'password|secret|token|credential|authorization|cookie|session|private[_-]?key|api[_-]?key', key, re.I)
                    else preview(child, field + '.' + key) for key, child in value.items()}
        if isinstance(value, list):
            if len(value) > limit: truncated.append({'field': field, 'total': len(value), 'shown': limit})
            return [preview(child, f'{field}[{index}]') for index, child in enumerate(value[:limit])]
        if isinstance(value, str):
            value = re.sub(r'(?i)(https?://)[^/\s]*@', r'\1[REDACTED]@', value)
            return re.sub(r'(?i)([?&](?:access_token|token|password|secret|api_key|key|signature)=)[^&#\s]*', r'\1[REDACTED]', value)
        return value
    result = preview(value)
    return {'path': audit.reference(relative), 'size_bytes': path.stat().st_size, 'class': audit.classify(audit.reference(relative)),
            'preview': result, 'truncated_arrays': truncated, 'more_jsonl_records': more,
            'note': '읽기 전용 미리보기입니다. 배열은 --limit 개수로 제한하고 인증 관련 필드·URL 자격증명은 가립니다.'}
