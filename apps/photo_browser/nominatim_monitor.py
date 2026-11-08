"""Session-local Nominatim monitoring; the web UI stays available during startup."""
import os
import threading
from collections import deque
from contextlib import contextmanager
from datetime import datetime

from nominatim_docker import (URL_ENV, NominatimStopped, _healthy,
                              managed_nominatim_docker, observe_nominatim, settings)


def timestamp():
    return datetime.now().astimezone().isoformat(timespec='seconds')


class NominatimMonitor:
    def __init__(self):
        self.lock = threading.Lock()
        self.events = deque(maxlen=200)
        self.state = {'enabled': False, 'phase': 'disabled', 'ready': False,
                      'message': '--nominatim-docker 옵션으로 실행하면 모니터링합니다.',
                      'error': None, 'started_at': None, 'ready_at': None,
                      'checked_at': None, 'endpoint': None, 'container': None,
                      'volume': None, 'image': None, 'progress': None}

    def update(self, **values):
        with self.lock:
            self.state.update(values, updated_at=timestamp())

    def record(self, message):
        message = message[-4000:]
        with self.lock:
            self.events.append({'time': timestamp(), 'message': message})
            if self.state['phase'] in {'ready', 'unavailable', 'error', 'stopping', 'stopped'}:
                return
            self.state['message'] = message
            self.state['updated_at'] = timestamp()
            if 'Docker 이미지 다운로드:' in message:
                self.state['phase'] = 'image_download'
            elif '지도 다운로드' in message:
                self.state['phase'] = 'map_download'
                self.state['progress'] = message
            elif '지도 DB 구축 중' in message:
                self.state['phase'] = 'database_import'
            elif 'Nominatim 실행을 시작합니다.' in message or 'Nominatim을 재사용합니다.' in message:
                self.state['phase'] = 'starting'

    def snapshot(self):
        with self.lock:
            return {**self.state, 'events': list(self.events)}

    @contextmanager
    def running(self, enabled, **options):
        if not enabled:
            yield
            return
        stop = threading.Event()
        try:
            config = settings(options['image'], options['pbf_url'], options['volume'], options['port'])
        except ValueError:
            # The worker reports invalid settings through the same monitoring UI.
            config = {'name': None, 'volume': options['volume'], 'image': options['image']}
        endpoint = f'http://127.0.0.1:{options["port"]}/reverse'
        self.update(enabled=True, phase='checking', started_at=timestamp(),
                    endpoint=endpoint, container=config['name'], volume=config['volume'],
                    image=config['image'], message='Docker 및 지도 DB 사전 점검 중')
        previous = os.environ.get(URL_ENV)
        # Direct scans to the local service even while it is being prepared.
        # The lookup layer already handles a service that is not ready yet.
        if not previous:
            os.environ[URL_ENV] = endpoint

        def worker():
            with observe_nominatim(self.record):
                try:
                    with managed_nominatim_docker(True, stop_event=stop, **options):
                        self.update(phase='ready', ready=True, ready_at=timestamp(),
                                    checked_at=timestamp(), message='Nominatim 실행 중 · 사용 가능')
                        while not stop.wait(3):
                            healthy = _healthy(endpoint.replace('/reverse', '/status?format=json'))
                            self.update(phase='ready' if healthy else 'unavailable', ready=healthy,
                                        checked_at=timestamp(),
                                        error=None if healthy else 'Nominatim 상태 API에 연결할 수 없거나 준비되지 않았습니다.',
                                        message='Nominatim 실행 중 · 사용 가능' if healthy else 'Nominatim 상태 확인 실패')
                except NominatimStopped:
                    pass
                except Exception as exc:
                    message = f'{type(exc).__name__}: {exc}'
                    print(f'Nominatim 오류: {message}', flush=True)
                    self.record(message)
                    self.update(phase='error', ready=False, error=message)
                finally:
                    if stop.is_set() and self.snapshot()['phase'] != 'error':
                        self.update(phase='stopped', ready=False, message='Nominatim 종료 처리 완료')

        thread = threading.Thread(target=worker, name='nominatim-lifecycle', daemon=True)
        thread.start()
        try:
            yield
        finally:
            stop.set()
            self.update(phase='stopping', ready=False, message='Nominatim 종료 처리 중')
            thread.join(timeout=130)
            if thread.is_alive():
                self.update(phase='error', error='Docker 종료가 지연되고 있습니다.')
            if previous is None:
                os.environ.pop(URL_ENV, None)
            else:
                os.environ[URL_ENV] = previous


def register_nominatim_monitor(app):
    monitor = NominatimMonitor()
    app.extensions['nominatim_monitor'] = monitor

    @app.get('/api/nominatim/status')
    def nominatim_status():
        from flask import jsonify
        response = jsonify(monitor.snapshot())
        response.headers['Cache-Control'] = 'no-store'
        return response
