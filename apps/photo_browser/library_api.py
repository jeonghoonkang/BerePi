"""Library HTTP API and single-worker background jobs."""
import hmac
import os
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from flask import abort, jsonify, request, send_file

from library import Library, atomic_json, component, now, read_json, uid


def register_library(app, boundary, db):
    library = Library(db, boundary)
    app.extensions['photo_library'] = library
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='photo-library')
    jobs, guard = {}, threading.Lock()
    controls = {}
    for path in (library.db / 'jobs').glob('*.json'):
        previous = read_json(path)
        if previous['status'] in {'queued', 'running', 'stopping'}:
            previous['status'] = 'interrupted'
            previous['warning'] = '서버가 재시작되었습니다. 이어하기 버튼으로 재개하세요.'
            atomic_json(path, previous)
        jobs[previous['job_id']] = previous
    tickets = {}

    @app.after_request
    def no_api_cache(response):
        if request.path.startswith('/api/') and not request.path.endswith('/file'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.before_request
    def protect():
        password = os.environ.get('PHOTO_BROWSER_PASSWORD')
        if password:
            auth = request.authorization
            if not auth or auth.type != 'basic' or not hmac.compare_digest(auth.password or '', password):
                return ('Authentication required', 401, {'WWW-Authenticate': 'Basic realm="Photo Browser"'})
        if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            origin = request.headers.get('Origin')
            if request.headers.get('X-Photo-Browser') != '1' or (origin and urlsplit(origin).netloc != request.host):
                abort(403, description='허용되지 않은 변경 요청입니다.')

    def body():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            abort(400, description='JSON 객체를 보내세요.')
        return data

    def ids(data):
        values = data.get('ids', [])
        if not isinstance(values, list) or len(values) > 10000 or any(not isinstance(v, str) for v in values):
            raise ValueError('올바른 미디어 ID 목록을 지정하세요.')
        return values

    def launch(function, kind=None, source_id=None):
        job_id = uid()
        stop = threading.Event()
        with guard:
            active = [j for j in jobs.values() if j['status'] in {'queued', 'running', 'stopping'}]
            if (kind == 'source_rename' and active) or any(j.get('kind') == 'source_rename' for j in active):
                raise ValueError('실행 중인 작업이 있습니다. 작업이 완료되거나 중지된 뒤 다시 시도하세요.')
            if kind == 'merge' and any(j.get('kind') == 'merge' and j['status'] in {'queued', 'running', 'stopping'} for j in jobs.values()):
                raise ValueError('이미 병합 작업이 실행 중입니다.')
            if kind == 'scan' and any(j.get('source_id') == source_id and j['status'] in {'queued', 'running', 'stopping'} for j in jobs.values()):
                raise ValueError('이 소스는 이미 스캔 중입니다.')
            jobs[job_id] = {'job_id': job_id, 'status': 'queued', 'kind': kind, 'source_id': source_id, 'created_at': now()}
            controls[job_id] = stop
            atomic_json(library.db / 'jobs' / (job_id + '.json'), jobs[job_id])
        def run():
            last_saved = 0
            def progress(state):
                nonlocal last_saved
                summary = {key: value for key, value in state.items() if key not in {'source', 'errors'}}
                summary['error_count'] = len(state.get('errors', []))
                with guard:
                    jobs[job_id]['progress'] = summary
                    if time.monotonic() - last_saved > 1:
                        atomic_json(library.db / 'jobs' / (job_id + '.json'), jobs[job_id])
                        last_saved = time.monotonic()
            with guard:
                jobs[job_id]['status'] = 'stopping' if stop.is_set() else 'running'
            try:
                result = function(progress, stop.is_set) if kind in {'scan', 'merge'} else function()
                update = {'status': result.get('status', 'completed') if kind in {'scan', 'merge'} else 'completed', 'result': result}
            except Exception as exc:
                update = {'status': 'failed', 'error': str(exc)}
            with guard:
                jobs[job_id].update(update, finished_at=now())
                atomic_json(library.db / 'jobs' / (job_id + '.json'), jobs[job_id])
                controls.pop(job_id, None)
        executor.submit(run)
        return jsonify(job_id=job_id), 202

    @app.errorhandler(ValueError)
    @app.errorhandler(KeyError)
    @app.errorhandler(TypeError)
    def invalid(exc):
        return jsonify(error=str(exc)), 400

    @app.errorhandler(OSError)
    def storage_error(exc):
        return jsonify(error='파일 작업 실패: ' + str(exc)), 409

    @app.get('/api/config')
    def get_config():
        return jsonify(library.config())

    @app.put('/api/config')
    def set_config():
        library.save_config(body())
        return jsonify(library.config())

    @app.post('/api/sources/check')
    def check_source():
        data = body()
        key = library.source_key(data)
        existing = next((s for s in library.config()['sources'] if library.source_key(s) == key), None)
        return jsonify(existing=existing)

    @app.post('/api/sources/rename')
    def rename_source():
        data = body()
        if data.get('background'):
            old, new = component(data['old_id']), component(data['new_id'])
            return launch(lambda: library.rename_source(old, new), 'source_rename', old)
        with guard:
            if any(j['status'] in {'queued', 'running', 'stopping'} for j in jobs.values()):
                raise ValueError('실행 중인 작업을 중지한 뒤 소스 ID를 변경하세요.')
            result = library.rename_source(data['old_id'], data['new_id'])
        return jsonify(result)

    @app.get('/api/jobs/<job_id>')
    def job_status(job_id):
        with guard:
            job = jobs.get(job_id)
            if not job:
                abort(404, description='작업이 없습니다.')
            return jsonify(job)

    @app.get('/api/jobs')
    def job_list():
        with guard:
            ordered = sorted(jobs.values(), key=lambda j: j['created_at'], reverse=True)
            limit = min(100, max(1, int(request.args.get('limit', 30))))
            offset = max(0, int(request.args.get('offset', 0)))
            return jsonify(items=ordered[offset:offset + limit], total=len(ordered), offset=offset, limit=limit)

    @app.post('/api/jobs/<job_id>/stop')
    def stop_scan(job_id):
        with guard:
            job = jobs.get(job_id)
            if not job or job.get('kind') not in {'scan', 'merge'}:
                raise ValueError('중지할 스캔 또는 병합 작업이 없습니다.')
            if job['status'] in {'queued', 'running', 'stopping'}:
                controls[job_id].set()
                job['status'] = 'stopping'
            return jsonify(job)

    @app.get('/api/scans')
    def scan_states():
        from scan_engine import scan_sessions
        with guard:
            active = {j.get('source_id') for j in jobs.values() if j['status'] in {'queued', 'running', 'stopping'}}
        sessions = scan_sessions(library)
        for state in sessions:
            if state['status'] == 'running' and state['source_id'] not in active:
                state['status'] = 'interrupted'
        return jsonify(items=sessions)

    @app.post('/api/scan')
    def scan():
        data = body()
        source_id, full = component(data['source_id']), data.get('full') is True
        mode = data.get('mode', 'incremental')
        if mode not in {'incremental', 'resume', 'restart'}:
            raise ValueError('올바른 스캔 모드를 지정하세요.')
        return launch(lambda progress, stopped: library.scan(source_id, full, mode, progress, stopped), 'scan', source_id)

    @app.get('/api/library')
    def list_media():
        items = library.items(request.args)
        state = request.args.get('state', 'active')
        items = [i for i in items if i['lifecycle']['status'] == state]
        for argument, key in [('event', 'events'), ('tag', 'tags'), ('person', 'person_ids')]:
            value = request.args.get(argument)
            if value:
                items = [i for i in items if value in i['classification'][key]]
        for argument, key in [('category', 'category_id'), ('owner', 'owner_id')]:
            value = request.args.get(argument)
            if value:
                items = [i for i in items if value == i['classification'][key]]
        if request.args.get('from'):
            items = [i for i in items if i['capture']['date_key'] >= request.args['from']]
        if request.args.get('to'):
            items = [i for i in items if i['capture']['date_key'] <= request.args['to']]
        if request.args.get('type'):
            items = [i for i in items if i['media_type'] == request.args['type']]
        query = request.args.get('q', '').casefold()
        if query:
            items = [i for i in items if query in (i['name'] + ' ' + ' '.join(i['classification']['events'] + i['classification']['tags'] + i['classification']['person_ids'])).casefold()]
        def chronology(item):
            capture = item['capture']
            value = capture.get('captured_at') or capture.get('filesystem_modified_at')
            try:
                stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=timezone.utc)
                timestamp = stamp.timestamp()
            except (ValueError, TypeError, AttributeError):
                timestamp = 0
            return capture['date_key'], timestamp, item['media_id']
        items.sort(key=chronology, reverse=True)
        window = None
        anchor = request.args.get('date')
        default_offset = 0
        if anchor:
            try:
                if date.fromisoformat(anchor).isoformat() != anchor:
                    raise ValueError
            except ValueError:
                abort(400, description='기준 날짜는 YYYY-MM-DD 형식이어야 합니다.')
            half = app.config['PHOTO_BROWSER_LIMIT'] // 2
            dated = [i for i in items if i['capture']['date_key'] != 'unknown']
            after = [i for i in dated if i['capture']['date_key'] > anchor]
            same = [i for i in dated if i['capture']['date_key'] == anchor]
            before = [i for i in dated if i['capture']['date_key'] < anchor]
            selected_after = after[-half:] if half else []
            selected_before = before[:half]
            items = selected_after + same + selected_before
            default_offset = len(selected_after) if same or selected_before else max(0, len(items) - 100)
            window = dict(date=anchor, per_side=half, before=len(selected_before),
                          on_date=len(same), after=len(selected_after),
                          before_total=len(before), after_total=len(after))
        offset = max(0, int(request.args.get('offset', default_offset)))
        limit = min(100, max(1, int(request.args.get('limit', 100))))
        return jsonify(total=len(items), items=items[offset:offset + limit], offset=offset, window=window)

    @app.get('/api/facets')
    def facets():
        result = {key: set() for key in ('events', 'tags', 'person_ids', 'category_id', 'owner_id')}
        for item in library.items():
            if item['lifecycle']['status'] == 'active':
                for key in result:
                    value = item['classification'][key]
                    result[key].update(value if isinstance(value, list) else [value])
        return jsonify({key: sorted(values) for key, values in result.items()})

    @app.get('/api/library/<media_id>')
    def get_media(media_id):
        item = next((i for i in library.items() if i['media_id'] == media_id), None)
        if not item:
            abort(404, description='미디어가 없습니다.')
        return jsonify(item)

    @app.patch('/api/library')
    def edit():
        data = body()
        library.edit(ids(data), data['changes'])
        return jsonify(ok=True)

    @app.post('/api/merge')
    def merge():
        data = body()
        values = ids(data)
        preview = data.get('preview', True)
        if not isinstance(preview, bool):
            raise ValueError('preview는 boolean이어야 합니다.')
        if preview:
            return launch(lambda: library.merge(values or None, True))
        resume = data.get('resume')
        if resume is not None:
            component(resume)
        return launch(lambda progress, stopped: library.merge(values or None, False, progress, stopped, resume), 'merge')

    @app.post('/api/verify')
    def verify():
        data = body()
        values, full = ids(data), data.get('full') is True
        return launch(lambda: library.verify(values, full))

    @app.get('/api/duplicates')
    def duplicates():
        return jsonify(library.duplicates())

    @app.get('/api/trash')
    def trash_list():
        return jsonify(items=library.trash_entries())

    @app.post('/api/trash')
    def trash():
        return jsonify(library.trash(ids(body())))

    @app.post('/api/trash/<trash_id>/restore')
    def restore(trash_id):
        return jsonify(library.restore(trash_id))

    @app.post('/api/trash/<trash_id>/prepare')
    def prepare(trash_id):
        entry = next((e for e in library.trash_entries() if e['trash_id'] == trash_id), None)
        if not entry or entry['status'] not in {'trashed', 'purge_failed'}:
            raise ValueError('삭제 가능한 휴지통 항목이 없습니다.')
        import time
        token = uid()
        tickets[token] = (trash_id, time.monotonic() + 300)
        return jsonify(token=token, phrase='영구 삭제 ' + trash_id[-6:], entry=entry)

    @app.post('/api/trash/<trash_id>/purge')
    def purge(trash_id):
        import time
        data = body()
        ticket = tickets.pop(data.get('token'), None)
        if not ticket or ticket[0] != trash_id or ticket[1] < time.monotonic() or data.get('phrase') != '영구 삭제 ' + trash_id[-6:]:
            raise ValueError('영구 삭제 확인이 만료되었거나 확인 문구가 다릅니다.')
        return jsonify(library.purge(trash_id))

    @app.get('/api/library/<media_id>/file')
    def library_file(media_id):
        item = next((i for i in library.items() if i['media_id'] == media_id and i['lifecycle']['status'] == 'active'), None)
        if not item:
            abort(404, description='미디어가 없습니다.')
        location = next((l for l in reversed(item['locations']) if l['role'] == 'managed' and l['status'] == 'available'), item['locations'][0])
        if location['protocol'] == 'file':
            path = library.local(location['path'])
        else:
            path = library.db / 'cache' / (item['sha256'] + Path(item['name']).suffix.lower())
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_name(uid() + '.tmp')
                try:
                    with library.materialize(location) as source:
                        from library import digest
                        if digest(source) != item['sha256']:
                            raise ValueError('원격 파일이 변경되었습니다. 재스캔하세요.')
                        shutil.copyfile(source, temporary)
                    os.replace(temporary, path)
                finally:
                    temporary.unlink(missing_ok=True)
        if not path.is_file():
            abort(404, description='파일이 없습니다.')
        return send_file(path, conditional=True)
