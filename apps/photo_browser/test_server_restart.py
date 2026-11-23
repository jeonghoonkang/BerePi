import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from server_restart import ServerRestart
from test_support import create_app


class ServerRestartTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.app = create_app(self.root, self.root, self.root / 'db')
        self.client = self.app.test_client()
        self.restart = self.app.extensions['server_restart']
        self.headers = {'X-Photo-Browser': '1'}

    def tearDown(self):
        self.temp.cleanup()

    def enable(self):
        self.restart.capture(['--db', str(self.root / 'db')])
        self.restart.enabled = True
        self.restart.shutdown = Mock()

    def test_wsgi_is_disabled_and_restart_requires_csrf(self):
        self.assertFalse(self.client.get('/api/server-lifecycle').json['supported'])
        self.assertEqual(self.client.post('/api/server-restart', json={}).status_code, 403)
        self.assertEqual(self.client.post('/api/server-restart', json={}, headers=self.headers).status_code, 409)
        self.assertFalse(self.restart.pending)
        invalid = {'Authorization': 'Basic aW52YWxpZDppbnZhbGlk', 'X-Photo-Browser': '1'}
        self.assertEqual(self.client.post('/api/server-restart', json={}, headers=invalid).status_code, 401)
        self.assertEqual(self.client.get('/api/server-lifecycle', headers=invalid).status_code, 401)

    def test_pending_restart_blocks_writes_and_repeated_requests(self):
        self.enable()
        with patch('server_restart.threading.Timer') as timer:
            accepted = self.client.post('/api/server-restart', json={'command': 'ignored'}, headers=self.headers)
            self.assertEqual(accepted.status_code, 202)
            self.assertTrue(accepted.json['pending'])
            self.assertEqual(self.client.post('/api/server-restart', json={}, headers=self.headers).status_code, 409)
            self.assertEqual(self.client.post('/api/merge', json={}, headers=self.headers).status_code, 503)
            self.assertEqual(self.client.get('/api/server-lifecycle').status_code, 200)
            self.assertNotIn('command', accepted.json)
            timer.return_value.start.assert_called_once()
            timer.call_args.args[1]()
            self.restart.shutdown.assert_called_once()

    def test_running_job_prevents_restart_until_stopped(self):
        self.enable()
        entered, release = threading.Event(), threading.Event()
        def scan(*args, **kwargs):
            entered.set()
            release.wait(5)
            return {'status': 'stopped'}
        with patch.object(self.app.extensions['photo_library'], 'scan', side_effect=scan):
            started = self.client.post('/api/scan', json={'source_id': 'test'}, headers=self.headers)
            try:
                self.assertEqual(started.status_code, 202)
                self.assertTrue(entered.wait(2))
                response = self.client.post('/api/server-restart', json={}, headers=self.headers)
                self.assertEqual(response.status_code, 409)
                self.assertIn('중지하고 저장', response.json['error'])
                self.assertFalse(self.restart.pending)
            finally:
                release.set()
            for _ in range(100):
                job = self.client.get('/api/jobs/' + started.json['job_id']).json
                if job['status'] == 'stopped':
                    break
                time.sleep(0.01)
            self.assertEqual(job['status'], 'stopped')

    def test_captured_python_flags_cwd_environment_and_safe_exec(self):
        original = ['python3', '-u', '-X', 'utf8', 'apps/photo_browser/app.py', '--port', '7007']
        with patch('server_restart.sys.orig_argv', original), patch.dict(os.environ, {'RESTART_TEST_MARKER': 'initial'}):
            restart = ServerRestart()
            restart.capture()
        restart.pending = True
        with patch('server_restart.os.chdir') as chdir, patch('server_restart.os.execve') as execute:
            restart.replace_process()
        self.assertEqual(restart.command[1:], original[1:])
        self.assertEqual(execute.call_args.args[2]['RESTART_TEST_MARKER'], 'initial')
        self.assertEqual(execute.call_args.args[:2], (restart.command[0], restart.command))
        chdir.assert_called_once_with(restart.cwd)

    def test_owned_server_drains_http_threads_and_disables_after_exit(self):
        server = Mock()
        server.__enter__ = Mock(return_value=server)
        server.__exit__ = Mock(return_value=False)
        self.restart.capture([])
        with patch('werkzeug.serving.make_server', return_value=server):
            self.restart.serve(self.app, '127.0.0.1', 0)
        self.assertFalse(server.daemon_threads)
        server.serve_forever.assert_called_once()
        self.assertFalse(self.restart.state()['supported'])


if __name__ == '__main__':
    unittest.main()
