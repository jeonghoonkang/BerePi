"""Read-only, restart-safe overview of settings → scan → publication → merge."""
import threading
from pathlib import Path

from library import component, read_json
from scan_engine import scan_sessions

ACTIVE = {'queued', 'running', 'stopping'}
ATTENTION = {'stopped', 'interrupted', 'paused_low_space', 'blocked_low_space', 'failed'}


def step(key, title, status='pending', percent=0, detail='앞 단계를 완료하면 진행할 수 있습니다.'):
    return {'id': key, 'title': title, 'status': status, 'percent': percent, 'detail': detail}


def percent(done, total):
    return round(min(100, max(0, done * 100 / total)), 1) if total else 0


class WorkflowStatus:
    def __init__(self, library):
        self.library = library
        self.lock = threading.Lock()
        self.generation = None
        self.catalog_cache = None
        self.merge_cache = {}
        self.job_error_cache = (None, 0)

    def merge_state(self):
        with self.lock:
            paths = set((self.library.db / 'merges').glob('*.json'))
            self.merge_cache = {p: value for p, value in self.merge_cache.items() if p in paths}
            for path in paths:
                stat = path.stat()
                signature = (stat.st_mtime_ns, stat.st_size)
                if path not in self.merge_cache or self.merge_cache[path][0] != signature:
                    state = read_json(path)
                    summary = {k: v for k, v in state.items() if k != 'operations' and k != 'ids'}
                    summary['operation_errors'] = sum(op.get('status') == 'error' for op in state.get('operations', []))
                    self.merge_cache[path] = (signature, summary)
            return dict(max((v[1] for v in self.merge_cache.values()), key=lambda s: s.get('updated_at', ''), default={}))

    def merge_job(self, job):
        progress = job.get('result') or job.get('progress') or {}
        key = (job.get('job_id'), job['status'], job.get('finished_at'))
        with self.lock:
            if key != self.job_error_cache[0]:
                self.job_error_cache = (key, sum(op.get('status') == 'error' for op in progress.get('operations', [])))
            errors = self.job_error_cache[1]
        return {k: v for k, v in progress.items() if k != 'operations'}, errors

    def catalog(self, managed):
        """Reuse immutable-generation counts; do not hash/stat every photo on polls."""
        index_path = self.library.db / 'index.json'
        manifest = read_json(index_path, {'chunks': []})
        key = (str(managed), index_path.exists(), tuple(c['path'] for c in manifest['chunks']))
        with self.lock:
            if key != self.generation:
                active = copied = 0
                for chunk in manifest['chunks']:
                    for item in read_json(self.library.db / chunk['path'])['items']:
                        if item['lifecycle']['status'] != 'active':
                            continue
                        active += 1
                        c, date = item['classification'], item['capture']['date_key']
                        year, month = (date[:4], date[5:7]) if date != 'unknown' else ('unknown', 'unknown')
                        parent = managed / c['category_id'] / c['owner_id'] / year / month
                        copied += any(loc['role'] == 'managed' and loc.get('status') == 'available'
                                      and Path(loc.get('path', '')).parent == parent for loc in item['locations'])
                self.catalog_cache = {'exists': key[1], 'active': active, 'copied': copied}
                self.generation = key
            return dict(self.catalog_cache)

    @staticmethod
    def scan_state(source, session, job):
        state = dict(session or {})
        if job:
            progress = dict(job.get('result') or job.get('progress') or {})
            same = progress.get('scan_id') and progress.get('scan_id') == state.get('scan_id')
            newer = job.get('created_at', '') >= state.get('created_at', '')
            if same or newer or (job['status'] in ACTIVE and not progress):
                if not same:
                    state = {'source': source}
                state.update(progress)
                state['status'] = job['status']
                state['job_error'] = job.get('error')
        if state and state.get('source') != source:
            return {'status': 'settings_changed'}
        return state

    def snapshot(self, jobs=()):
        library = self.library
        config = library.config()
        sources = config.get('sources', [])
        managed = Path(config['managed_root']).expanduser().resolve()
        steps = [step('settings', 'ID·소스 설정', detail='소스 ID·카테고리·소유자와 관리 경로를 저장하세요.'),
                 step('scan', '스캔·JSON 생성'), step('database', 'DB 구성·반영'),
                 step('merge', '관리 디렉토리 병합')]
        try:
            library.local(managed)
            if managed == library.boundary or managed.is_relative_to(library.db) or library.db.is_relative_to(managed):
                raise ValueError('관리 경로는 허용 루트 내부이며 DB와 분리되어야 합니다.')
            for source in sources:
                component(source['source_id'])
                component(source.get('category', 'family'))
                component(source.get('owner_id', 'default'))
                if not source.get('root'):
                    raise ValueError('원본 경로를 저장하세요.')
            if sources:
                steps[0].update(status='completed', percent=100, detail=f'{len(sources):,}개 소스의 ID·분류·소유자와 관리 경로 저장 완료')
        except ValueError as exc:
            steps[0].update(status='warning', detail=str(exc))

        latest_jobs = {}
        for job in jobs:
            if job.get('kind') not in {'scan', 'merge'}:
                continue
            key = (job['kind'], job.get('source_id') if job['kind'] == 'scan' else None)
            if key not in latest_jobs or latest_jobs[key]['created_at'] < job['created_at']:
                latest_jobs[key] = job
        sessions = {s['source_id']: s for s in scan_sessions(library)}
        states = [self.scan_state(s, sessions.get(s['source_id']), latest_jobs.get(('scan', s['source_id']))) for s in sources]
        errors = sum(len(s.get('errors', [])) or s.get('error_count', 0) for s in states)
        finished = lambda s: bool(s.get('inventory_complete') and s.get('processed', 0) == s.get('total', 0)
                                  and not (s.get('errors') or s.get('error_count'))
                                  and s.get('status') in {'completed', 'running'}
                                  and (s.get('phase') in {'publishing', 'done'} or s.get('status') == 'completed'))
        scanned = sum(finished(s) for s in states)
        published = sum(finished(s) and s.get('published') is True and s.get('status') == 'completed' for s in states)
        running = [s for s in states if s.get('status') in ACTIVE]
        listing = any(s.get('phase', 'listing') == 'listing' and not s.get('inventory_complete') for s in running)
        processed = sum(s.get('processed', 0) for s in states)
        total = sum(s.get('total', 0) for s in states)
        trouble = [s for s in states if s.get('status') in ATTENTION or s.get('job_error')]
        changed = any(s.get('status') == 'settings_changed' for s in states)
        if sources and steps[0]['status'] == 'completed':
            unlisted = sum(not s.get('inventory_complete') for s in states)
            # Unscanned sources have no known file total. Do not show 100% after
            # finishing only the first of several sources.
            scan_percent = (round(sum(100 if finished(s) else percent(s.get('processed', 0), s.get('total', 0))
                                      for s in states) / len(sources), 1) if unlisted else percent(processed, total))
            detail = f'소스 {scanned}/{len(sources)} 완료 · 집계된 파일 {processed:,}/{total:,}개 처리'
            if unlisted:
                detail += f' · 미집계 소스 {unlisted}개'
            steps[1].update(detail=detail, percent=None if listing else scan_percent)
            if scanned == len(sources):
                steps[1].update(status='completed', percent=100)
            elif running:
                steps[1].update(status='running', detail=detail + (' · 목록 집계 중 (전체 개수 확인 중)' if listing else ''))
            elif trouble or errors or changed:
                status = 'failed' if any(s.get('status') == 'failed' for s in trouble) else 'warning'
                message = '설정 변경 · 새 스캔 필요' if changed else f'중지·오류 확인 후 재개 필요 · 오류 {errors:,}개'
                steps[1].update(status=status, detail=detail + ' · ' + message)
            elif any(states):
                steps[1].update(detail=detail + ' · 나머지 소스를 스캔하세요.')
            else:
                steps[1].update(detail='등록된 소스에서 스캔 / JSON 생성을 실행하세요.')

        catalog = self.catalog(managed)
        publishing = any(s.get('phase') == 'publishing' for s in running)
        db_detail = f'소스 {published}/{len(sources)} 발행 완료 · 활성 미디어 {catalog["active"]:,}개'
        if sources and published == len(sources) and catalog['exists']:
            steps[2].update(status='completed', percent=100, detail=db_detail)
        elif publishing:
            steps[2].update(status='running', percent=None, detail=db_detail + ' · 월별 JSON·인덱스 반영 중')
        elif sources and (any(s.get('published') for s in states) or catalog['exists']):
            steps[2].update(status='warning' if trouble or errors or changed or scanned == len(sources) else 'pending',
                            percent=percent(published, len(sources)), detail=db_detail + ' · 현재 스캔의 전체 반영 대기')
        elif sources and scanned == len(sources):
            steps[2].update(status='warning', detail='스캔은 끝났지만 DB 발행이 완료되지 않았습니다. 공간·오류를 확인하세요.')

        # CLI merge sessions are persisted even when no web job exists.
        merge = self.merge_state()
        job = latest_jobs.get(('merge', None))
        if job:
            progress, operation_errors = self.merge_job(job)
            if (job['status'] in ACTIVE or progress.get('merge_id') == merge.get('merge_id')
                    or job['created_at'] >= merge.get('updated_at', '')):
                merge = {**progress, 'status': job['status'], 'operation_errors': operation_errors}
        coverage = percent(catalog['copied'], catalog['active'])
        merge_detail = f'관리 복사본 등록 {catalog["copied"]:,}/{catalog["active"]:,}개 (현재 분류 경로 기준)'
        steps[3].update(percent=coverage, detail=merge_detail)
        status = merge.get('status')
        ready = steps[2]['status'] == 'completed'
        if status in ACTIVE:
            phase = merge.get('phase')
            detail = (f'복사 용량·여유 공간 확인 중 · {merge.get("checked", 0):,}개 확인' if phase == 'checking_space' else
                      f'병합 보고서용 파일 집계 중 · {merge.get("report_files", 0):,}개 확인' if phase == 'report_inventory' else
                      'DB와 병합 설정 읽는 중' if phase == 'loading' else
                      f'병합 {merge.get("processed", 0):,}/{merge.get("total", 0):,}개 처리')
            steps[3].update(status='running', percent=merge.get('percent'),
                            detail=detail + ' · ' + merge_detail)
        elif status in ATTENTION:
            reason = {'blocked_low_space': '공간 부족', 'paused_low_space': '공간 부족', 'failed': '병합 실패',
                      'stopped': '병합 중지', 'interrupted': '병합 중단'}[status]
            steps[3].update(status='failed' if status == 'failed' else 'warning', detail=reason + ' · ' + merge_detail)
        elif merge.get('operation_errors'):
            steps[3].update(status='warning', detail='일부 파일 병합 오류 · ' + merge_detail)
        elif ready and catalog['active'] and catalog['copied'] == catalog['active']:
            steps[3].update(status='completed', percent=100)
        elif ready and not catalog['active']:
            steps[3].update(percent=0, detail='병합할 활성 파일이 없습니다. 소스와 스캔 결과를 확인하세요.')
        elif ready:
            steps[3].update(status='warning' if catalog['copied'] else 'pending', detail=merge_detail + ' · 미리보기 후 병합을 실행하세요.')
        else:
            steps[3].update(status='pending', percent=0, detail=merge_detail + ' · 스캔·DB 반영 완료 대기')

        complete = sum(s['status'] == 'completed' for s in steps)
        overall = sum(100 if s['status'] == 'completed' else min(99, s['percent'] or 0) for s in steps) / len(steps)
        return {'steps': steps, 'completed_steps': complete, 'total_steps': len(steps),
                'percent': 100 if complete == len(steps) else min(99.9, round(overall, 1)),
                'note': '단계별 동일 가중치 진행률입니다. 남은 시간 예측이 아니며 복사 상태는 DB 등록 기준입니다.'}
