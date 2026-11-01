"""Human-readable UTF-8 copies of finished job records."""
import json
from datetime import datetime, timedelta, timezone

from library import component, now
from merge_history import atomic_text

ACTIVE_STATES = {'queued', 'running', 'stopping'}
KST = timezone(timedelta(hours=9))


def display_time(value):
    if not value:
        return '기록 없음'
    try:
        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if date.tzinfo is None:
            return str(value) + ' (시간대 미기록)'
        return date.astimezone(KST).strftime('%Y-%m-%d %H:%M:%S KST')
    except (ValueError, TypeError, AttributeError):
        return str(value) + ' (날짜 형식 확인 필요)'


def archive_job(db, job):
    if job['status'] in ACTIVE_STATES:
        raise ValueError('작업이 종료된 뒤 보관할 수 있습니다.')
    path = db / 'job-archives' / (component(job['job_id']) + '.txt')
    saved_at = now()
    detail = job.get('result') or job.get('progress') or {}
    lines = ['Photo Browser 작업 보관 기록',
             f"작업 ID: {job['job_id']}", f"종류: {job.get('kind') or '기록 없음'}",
             f"소스 ID: {job.get('source_id') or '전체 / 해당 없음'}",
             f"상태: {job['status']}",
             f"등록 시각: {display_time(job.get('created_at'))}",
             f"시작 시각: {display_time(job.get('started_at'))}",
             f"완료 / 종료 시각: {display_time(job.get('finished_at'))}",
             f"최초 병합 시작: {display_time(job.get('merge_started_at') or detail.get('merge_started_at'))}",
             f'보관 시각: {display_time(saved_at)}', f'JSON DB: {db}', f'TXT 보관 경로: {path}', '']
    labels = {'total': '전체 개수', 'processed': '처리 개수', 'percent': '진행률 (%)',
              'added': '신규', 'updated': '갱신', 'unchanged': '변경 없음', 'ignored': '제외',
              'published': 'DB 반영', 'current_file': '마지막 처리 파일',
              'current_action': '마지막 처리 동작', 'source_file': '원본 소스', 'target_file': '관리 대상 경로'}
    for key, label in labels.items():
        if key in detail:
            lines.append(f'{label}: {detail[key]}')
    if 'errors' in detail or 'error_count' in detail:
        lines.append(f"처리 오류 개수: {len(detail['errors']) if isinstance(detail.get('errors'), list) else detail.get('error_count', 0)}")
    for key in ('error', 'warning'):
        if job.get(key) or detail.get(key):
            lines.append(f"{key}: {job.get(key) or detail[key]}")
    lines.extend(['', '전체 작업 기록 (JSON)', json.dumps(job, ensure_ascii=False, indent=2), ''])
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_text(path, '\n'.join(lines))
    return {'path': str(path), 'saved_at': saved_at}
