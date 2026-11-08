import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from app import create_app
from nominatim_docker import DEFAULT_IMAGE, DEFAULT_PBF, DEFAULT_VOLUME
from nominatim_monitor import NominatimMonitor

OPTIONS = dict(image=DEFAULT_IMAGE, pbf_url=DEFAULT_PBF, volume=DEFAULT_VOLUME, port=8080, timeout=10)


def wait_for(predicate):
    deadline = time.monotonic() + 5
    while not predicate() and time.monotonic() < deadline:
        time.sleep(.01)
    assert predicate(), 'Monitor did not reach the expected state'


class NominatimMonitorTests(unittest.TestCase):
    def test_disabled_status_and_separate_tab(self):
        with tempfile.TemporaryDirectory() as folder:
            client = create_app(folder, folder, Path(folder) / 'db').test_client()
            response = client.get('/api/nominatim/status')
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json['enabled'])
            self.assertEqual(response.json['phase'], 'disabled')
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            page = client.get('/').get_data(as_text=True)
            self.assertIn('data-tab="nominatim-panel"', page)
            self.assertIn('id="nominatim-panel"', page)
            self.assertIn('nominatim.js', page)

    def test_preparing_ready_and_shutdown_are_observable(self):
        monitor = NominatimMonitor()
        prepare = threading.Event()
        cleaned = threading.Event()

        @contextmanager
        def lifecycle(*args, stop_event, **kwargs):
            try:
                while not prepare.wait(.01):
                    if stop_event.is_set():
                        return
                yield
            finally:
                cleaned.set()

        with patch('nominatim_monitor.managed_nominatim_docker', lifecycle):
            with monitor.running(True, **OPTIONS):
                self.assertEqual(monitor.snapshot()['phase'], 'checking')
                self.assertFalse(monitor.snapshot()['ready'])
                prepare.set()
                wait_for(lambda: monitor.snapshot()['ready'])
                monitor.record('late Docker log')
                self.assertEqual(monitor.snapshot()['phase'], 'ready')
                self.assertEqual(monitor.snapshot()['message'], 'Nominatim 실행 중 · 사용 가능')
            self.assertTrue(cleaned.is_set())
            self.assertEqual(monitor.snapshot()['phase'], 'stopped')

    def test_failure_is_available_in_status_without_stopping_web(self):
        with tempfile.TemporaryDirectory() as folder:
            app = create_app(folder, folder, Path(folder) / 'db')
            monitor = app.extensions['nominatim_monitor']
            with patch('nominatim_monitor.managed_nominatim_docker', side_effect=ValueError('Docker 실행 파일이 없습니다.')):
                with monitor.running(True, **OPTIONS):
                    wait_for(lambda: monitor.snapshot()['phase'] == 'error')
                    client = app.test_client()
                    self.assertEqual(client.get('/').status_code, 200)
                    result = client.get('/api/nominatim/status').json
                    self.assertFalse(result['ready'])
                    self.assertIn('Docker 실행 파일이 없습니다.', result['error'])

    def test_events_are_bounded_and_download_stage_is_preserved(self):
        monitor = NominatimMonitor()
        monitor.update(phase='checking')
        monitor.record('Nominatim 지도 다운로드 · 50% · 남은 시간 0:00:50')
        self.assertEqual(monitor.snapshot()['phase'], 'map_download')
        self.assertIn('50%', monitor.snapshot()['progress'])
        for i in range(250):
            monitor.record(f'log {i}')
        result = monitor.snapshot()
        self.assertEqual(len(result['events']), 200)
        self.assertEqual(result['events'][-1]['message'], 'log 249')


if __name__ == '__main__':
    unittest.main()
