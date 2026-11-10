"""Small progress snapshots and read-only merge status lookup."""
import time
from pathlib import Path

from library import atomic_json, component, now, read_json, uid
from merge_estimate import ETA_FIELDS


class MergeProgress:
    def __init__(self, db, merge_id, started_at):
        self.path = Path(db) / 'merge-progress' / (uid() + '.json')
        self.state = {'merge_id': merge_id, 'status': 'running', 'run_started_at': started_at}
        self.last_saved = None

    def update(self, value, force=False):
        value = dict(value)
        if value.get('phase') == 'report_inventory':
            value['current_action'] = 'report_inventory'
            if self.state.get('total') is not None:
                value.pop('processed', None)
        # Publish before potentially long copy/hash calls, even within one second.
        force = force or value.get('current_action') in {'copying', 'verifying_copy', 'comparing_existing'}
        self.state.update({key: item for key, item in value.items()
                           if key not in {'operations', 'ids', 'settings', 'history_report'}})
        clock = time.monotonic()
        if force or self.last_saved is None or clock - self.last_saved >= 1:
            self.state['updated_at'] = now()
            atomic_json(self.path, self.state)
            self.last_saved = clock


FIELDS = ('merge_id', 'status', 'phase', 'processed', 'total', 'percent', 'current_file',
          'fast_skipped_count',
          'current_file_role', 'current_action', 'source_file', 'target_file',
          'merge_started_at', 'run_started_at', 'updated_at', 'warning', 'error',
          'merge_elapsed_seconds', 'estimated_total_seconds') + ETA_FIELDS


def merge_status(db, merge_id=None):
    """Read snapshots without initializing Library or taking its writer lock."""
    db = Path(db)
    if not db.is_dir():
        raise ValueError(f'DB 디렉토리가 없습니다: {db}')
    if merge_id:
        component(merge_id)
    candidates, errors = [], []
    for directory in ('merges', 'jobs', 'merge-progress'):
        for path in (db / directory).glob('*.json'):
            try:
                record = read_json(path)
                if not isinstance(record, dict):
                    raise ValueError('상태 기록은 JSON 객체여야 합니다.')
                if directory == 'jobs':
                    if record.get('kind') != 'merge':
                        continue
                    detail = record.get('result') or record.get('progress') or {}
                    value = {**detail, **{key: record[key] for key in
                             ('status', 'error', 'warning') if key in record}}
                    value.setdefault('run_started_at', record.get('started_at') or record.get('created_at'))
                    value['job_id'] = record.get('job_id', path.stem)
                else:
                    value = record
                if merge_id and value.get('merge_id') != merge_id:
                    continue
                if not value.get('status'):
                    raise ValueError('상태 기록에 status가 없습니다.')
                modified = path.stat().st_mtime_ns
                summary = {key: value.get(key) for key in FIELDS}
                summary.update(record_file=str(path), record_type=directory,
                               job_id=value.get('job_id'))
                candidates.append((modified, summary))
            except FileNotFoundError:
                continue  # A job or checkpoint was removed during the read.
            except (OSError, ValueError, TypeError, AttributeError) as exc:
                errors.append({'file': str(path), 'error': str(exc)})
    candidates.sort(key=lambda entry: entry[0], reverse=True)
    if merge_id and not candidates:
        raise ValueError(f'병합 기록을 찾지 못했습니다: {merge_id}')
    return {'db': str(db), 'observed_at': now(),
            'items': [candidates[0][1]] if candidates else [], 'errors': errors,
            'message': '저장된 최신 상태입니다. 프로세스의 실행 여부를 보장하지 않습니다.' if candidates
                       else '병합 기록이 없습니다.'}
