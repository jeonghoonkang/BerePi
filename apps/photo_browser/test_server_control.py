import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from urllib.request import Request, urlopen
import base64

from db_locks import exclusive_file_lock
from library import atomic_json
from server_control import (HISTORY, REQUEST, RUNTIME, LocalServerControl,
                            ensure_server_stopped, history, record_history)
import test_db_prune


class ServerControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name).resolve()
        self.controller = SimpleNamespace(instance_id='current-instance', lock=threading.Lock(),
                                          pending=False, stopping=False, shutdown=Mock())
        self.jobs = Mock(return_value=0)
        self.app = SimpleNamespace(extensions={'photo_jobs_maintenance': self.jobs})

    def control(self):
        control = LocalServerControl(self.db, self.controller, self.app, '127.0.0.1', 7000)
        control.start()
        self.addCleanup(control.stop_watching)
        return control

    def test_no_server_does_not_trust_or_signal_stale_pid(self):
        atomic_json(self.db / RUNTIME, {'pid': os.getpid(), 'instance_id': 'stale'})
        ensure_server_stopped(self.db, stream=io.StringIO())
        self.assertFalse((self.db / REQUEST).exists())

    def test_locked_unknown_server_is_not_killed(self):
        with exclusive_file_lock(self.db / '.server.lock'):
            with self.assertRaisesRegex(ValueError, '실행 기록'):
                ensure_server_stopped(self.db, timeout=0.01, stream=io.StringIO())
        self.assertFalse((self.db / REQUEST).exists())

    def test_wrong_instance_requests_are_ignored(self):
        self.control()
        atomic_json(self.db / REQUEST, {'db': str(self.db), 'instance_id': 'old-instance',
                                       'action': 'stop_for_maintenance'})
        time.sleep(0.45)
        self.controller.shutdown.assert_not_called()
        self.assertFalse(self.controller.stopping)

    def test_request_for_another_db_is_ignored(self):
        self.control()
        atomic_json(self.db / REQUEST, {'db': str(self.db / 'another-db'),
                                       'instance_id': self.controller.instance_id,
                                       'action': 'stop_for_maintenance'})
        time.sleep(0.45)
        self.controller.shutdown.assert_not_called()
        self.assertFalse(self.controller.stopping)

    def test_shutdown_waits_for_cooperative_jobs(self):
        self.jobs.return_value = 1
        control = self.control()
        atomic_json(self.db / REQUEST, {'db': str(self.db), 'instance_id': self.controller.instance_id,
                                       'action': 'stop_for_maintenance'})
        deadline = time.monotonic() + 2
        while not self.controller.stopping and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(self.controller.stopping)
        self.controller.shutdown.assert_not_called()
        self.jobs.return_value = 0
        deadline = time.monotonic() + 2
        while not self.controller.shutdown.called and time.monotonic() < deadline:
            time.sleep(0.02)
        self.controller.shutdown.assert_called_once()
        control.finish()
        self.assertEqual(history(self.db)[-1]['state'], 'stopped')

    def test_busy_server_timeout_prevents_maintenance(self):
        atomic_json(self.db / RUNTIME, {'pid': os.getpid(), 'instance_id': 'unresponsive',
                                       'state': 'running', 'db': str(self.db)})
        with exclusive_file_lock(self.db / '.server.lock'):
            with self.assertRaisesRegex(ValueError, '정리를 실행하지 않습니다'):
                ensure_server_stopped(self.db, timeout=0.01, stream=io.StringIO())

    def test_history_is_bounded_to_latest_1000_records(self):
        (self.db / HISTORY).write_text(''.join(json.dumps({'event': i}) + '\n' for i in range(1000)))
        record_history(self.db, {'event': 1000})
        rows = history(self.db)
        self.assertEqual(len(rows), 1000)
        self.assertEqual(rows[0]['event'], 1)
        self.assertEqual(rows[-1]['event'], 1000)


class ServerControlProcessTests(unittest.TestCase):
    write = test_db_prune.DBPruneTests.write

    def setUp(self):
        test_db_prune.DBPruneTests.setUp(self)

    def test_cli_stops_real_server_saves_running_scan_and_reuses_history(self):
        wrapper = self.root / 'start.py'
        wrapper.write_text(
            'import sys, time\n'
            f'sys.path.insert(0, {str(Path(__file__).resolve().parent)!r})\n'
            'from library import Library\n'
            'original_scan = Library.scan\n'
            'def slow_scan(self, source_id, full=False, mode="incremental", progress=None, stopped=None):\n'
            '    progress({"phase":"waiting_for_stop", "processed":0})\n'
            '    while not stopped(): time.sleep(0.05)\n'
            '    (self.db / "scan-saved-marker.txt").write_text("stop requested")\n'
            '    return original_scan(self, source_id, full, mode, progress, stopped)\n'
            'Library.scan = slow_scan\n'
            'from app import main\nmain()\n', encoding='utf-8')
        environment = {**os.environ, 'PHOTO_BROWSER_PASSWORD': 'control-test-only', 'PYTHONUTF8': '1'}
        command = [sys.executable, '-u', str(wrapper), '--root', str(self.root), '--db', str(self.db),
                   '--directory', str(self.source), '--port', '0', '--source-check-interval', '0',
                   '--version-log-interval', '0']
        with (self.root / 'server.log').open('w', encoding='utf-8') as log:
            process = subprocess.Popen(command, cwd=self.root, env=environment, stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 20
                record = None
                while time.monotonic() < deadline:
                    if (self.db / RUNTIME).exists():
                        record = json.loads((self.db / RUNTIME).read_text(encoding='utf-8'))
                        break
                    if process.poll() is not None:
                        self.fail((self.root / 'server.log').read_text(encoding='utf-8'))
                    time.sleep(0.05)
                self.assertIsNotNone(record)
                auth = 'Basic ' + base64.b64encode(b'test:control-test-only').decode()
                request = Request(f'http://127.0.0.1:{record["port"]}/api/scan',
                                  data=b'{"source_id":"photos"}',
                                  headers={'Authorization': auth, 'Content-Type': 'application/json',
                                           'X-Photo-Browser': '1'})
                with urlopen(request, timeout=5) as response:
                    job_id = json.load(response)['job_id']
                # Exercise recovery via local history when the live record was lost.
                (self.db / RUNTIME).unlink()
                cli = Path(__file__).with_name('cli.py')
                result = subprocess.run([sys.executable, str(cli), '--db', str(self.db), 'db-prune-plan',
                                         '--plan', str(self.plan), '--under', self.folder, '--server-stopped',
                                         '--server-stop-timeout', '15'], env=environment,
                                        capture_output=True, text=True, encoding='utf-8', timeout=25)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('서버 종료 확인 완료', result.stderr)
                process.wait(timeout=10)
                self.assertEqual(process.returncode, 0, (self.root / 'server.log').read_text(encoding='utf-8'))
                self.assertTrue((self.db / 'scan-saved-marker.txt').exists())
                job = json.loads((self.db / 'jobs' / (job_id + '.json')).read_text(encoding='utf-8'))
                self.assertEqual(job['status'], 'stopped')
                self.assertEqual(history(self.db)[-1]['state'], 'stopped')
                self.assertTrue(self.old.exists())  # Planning never deletes.
                report = json.loads(result.stdout)
                result = subprocess.run([sys.executable, str(cli), '--db', str(self.db), 'db-prune-apply',
                                         '--plan', str(self.plan), '--server-stopped', '--confirm', report['plan_id']],
                                        env=environment, capture_output=True, text=True, encoding='utf-8', timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(self.old.exists())
                self.assertTrue((self.source / 'photo.jpg').exists())
                self.assertTrue(Path(self.item['locations'][-1]['path']).exists())
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)


if __name__ == '__main__':
    unittest.main()
