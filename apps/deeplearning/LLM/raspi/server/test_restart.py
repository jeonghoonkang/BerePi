"""Offline HTTP/process regressions for LAN discovery and authenticated restart."""
import json
import os
from pathlib import Path
import socket
import signal
import tempfile
import subprocess
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import Mock, patch

from server import Config, Server, local_ipv4_addresses


class AddressTests(unittest.TestCase):
    def test_only_valid_lan_addresses_are_deduplicated_and_192_first(self):
        output = '10.0.0.9 192.168.1.20 192.168.1.3 192.168.1.20 ::1 127.0.0.1 8.8.8.8 invalid'
        with patch('server.subprocess.run', return_value=Mock(stdout=output)):
            self.assertEqual(local_ipv4_addresses(), ['192.168.1.3', '192.168.1.20', '10.0.0.9'])

    def test_discovery_failure_is_nonfatal(self):
        for error in (OSError(), subprocess.TimeoutExpired('hostname', 3)):
            with patch('server.subprocess.run', side_effect=error):
                self.assertEqual(local_ipv4_addresses(), [])


class RestartTests(unittest.TestCase):
    def setUp(self):
        self.key = 'restart-test-' + 'x' * 32
        with patch.dict(os.environ, {'GEMMA4_API_KEY': self.key}, clear=True):
            config = Config()
        self.server = Server(('127.0.0.1', 0), config)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(self, path, data=None, authenticated=True, origin=None):
        headers = {'Content-Type': 'application/json'}
        if authenticated:
            headers['Authorization'] = 'Bearer ' + self.key
        if origin:
            headers['Origin'] = origin
        request = urllib.request.Request(self.base + path, headers=headers,
                                         data=None if data is None else json.dumps(data).encode())
        try:
            response = self.opener.open(request, timeout=5)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, json.load(response)

    def test_status_exposes_local_urls_with_configured_port(self):
        self.server.config.port = 8089
        with patch('server.local_ipv4_addresses', return_value=['192.168.0.10', '10.0.0.2']), \
             patch.object(self.server, 'backend_json', return_value={'models': []}):
            status, data = self.request('/api/status')
        self.assertEqual(status, 200)
        self.assertEqual(data['local_urls'], ['http://192.168.0.10:8089', 'http://10.0.0.2:8089'])

    def test_unauthorized_foreign_origin_and_invalid_body_cannot_restart(self):
        self.assertEqual(self.request('/api/restart', {}, authenticated=False)[0], 401)
        self.assertEqual(self.request('/api/restart', {}, origin='http://other.test')[0], 403)
        self.assertEqual(self.request('/api/restart', {'command': 'anything'})[0], 400)
        self.assertFalse(self.server.restart_requested.is_set())
        self.assertFalse(self.server.inference.locked())

    def test_busy_inference_is_preserved(self):
        with self.server.inference:
            self.assertEqual(self.request('/api/restart', {})[0], 409)
        self.assertFalse(self.server.restart_requested.is_set())
        self.assertEqual(self.request('/api/health', authenticated=False)[0], 200)

    def test_response_is_returned_before_server_stops(self):
        instance = self.request('/api/health', authenticated=False)[1]['instance_id']
        status, result = self.request('/api/restart', {})
        self.assertEqual(status, 202)
        self.assertEqual(result, {'restarting': True, 'instance_id': instance})
        self.thread.join(timeout=5)
        self.assertFalse(self.thread.is_alive())
        self.assertTrue(self.server.restart_requested.is_set())
        self.assertTrue(self.server.inference.locked())

    def test_duplicate_restart_and_new_inference_rejected(self):
        stopped = threading.Event()
        with patch.object(self.server, 'shutdown', side_effect=stopped.set):
            self.assertEqual(self.request('/api/restart', {})[0], 202)
            self.assertTrue(stopped.wait(2))
            self.assertEqual(self.request('/api/restart', {})[0], 409)
            self.assertEqual(self.request('/api/chat', {'messages': [{'role': 'user', 'content': 'hi'}]})[0], 429)


class ProcessRestartTests(unittest.TestCase):
    def run_restart(self, managed):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        env = os.environ.copy()
        env.update(GEMMA4_SERVER_HOST='127.0.0.1', GEMMA4_SERVER_PORT=str(port),
                   GEMMA4_API_KEY='process-test-' + 'a' * 32)
        env.pop('GEMMA4_MANAGED_LAUNCHER', None)
        if managed:
            env['GEMMA4_MANAGED_LAUNCHER'] = '1'
        process = subprocess.Popen([sys.executable, str(Path(__file__).with_name('server.py'))],
                                   env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        base = f'http://127.0.0.1:{port}'

        def healthy(different_from=None):
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                try:
                    with opener.open(base + '/api/health', timeout=1) as response:
                        data = json.load(response)
                    if data['instance_id'] != different_from and not data['restarting']:
                        return data['instance_id']
                except (OSError, ValueError):
                    pass
                time.sleep(0.05)
            self.fail('Server did not start/restart on its original port')

        try:
            before = healthy()
            request = urllib.request.Request(base + '/api/restart', data=b'{}', headers={
                'Authorization': 'Bearer ' + env['GEMMA4_API_KEY'], 'Content-Type': 'application/json'})
            with opener.open(request, timeout=5) as response:
                self.assertEqual(response.status, 202)
            if managed:
                self.assertEqual(process.wait(timeout=10), 75)
            else:
                self.assertNotEqual(healthy(before), before)
                self.assertIsNone(process.poll())
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=5)

    def test_standalone_process_restarts_on_same_port(self):
        self.run_restart(managed=False)

    def test_managed_process_returns_launcher_restart_code(self):
        self.run_restart(managed=True)


class LauncherRestartTests(unittest.TestCase):
    def test_managed_restart_reloads_config_and_restarts_only_owned_children(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tools = root / 'tools'
            tools.mkdir()
            (root / 'run_service.sh').write_bytes(Path(__file__).with_name('run_service.sh').read_bytes())
            (root / 'config.env').write_text('RESTART_TEST_SETTING=original\n')
            events = root / 'events'
            implementations = {
                'uname': "print('Linux' if sys.argv[1] == '-s' else 'aarch64')",
                'curl': 'pass',
                'flock': "import fcntl; fcntl.flock(9, fcntl.LOCK_EX | fcntl.LOCK_NB)",
                'ollama': """if sys.argv[1] == 'serve':
    with open(os.environ['RESTART_TEST_EVENTS'], 'a') as output:
        output.write('ollama\\n')
    os.execvp('sleep', ['sleep', '60'])
""",
                'python3': """if sys.argv[1] == '-':
    sys.stdin.read()
else:
    events = Path(os.environ['RESTART_TEST_EVENTS'])
    before = events.read_text() if events.exists() else ''
    with events.open('a') as output:
        output.write('server ' + os.environ.get('GEMMA4_MANAGED_LAUNCHER', '') + ' ' + os.environ['RESTART_TEST_SETTING'] + '\\n')
    time.sleep(0.2)
    if 'server ' not in before:
        Path('config.env').write_text('RESTART_TEST_SETTING=updated\\n')
        sys.exit(75)
    sys.exit(23)
""",
            }
            for name, body in implementations.items():
                executable = tools / name
                executable.write_text('#!' + sys.executable + '\nimport os, sys, time\nfrom pathlib import Path\n' + body + '\n')
                executable.chmod(0o700)
            env = os.environ.copy()
            env.update(PATH=str(tools) + os.pathsep + env['PATH'], RESTART_TEST_EVENTS=str(events))
            process = subprocess.Popen(['/bin/bash', str(root / 'run_service.sh')], env=env,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                       start_new_session=True)
            try:
                output, _ = process.communicate(timeout=20)
                self.assertEqual(process.returncode, 23, output)
                records = events.read_text().splitlines()
                self.assertEqual(records.count('ollama'), 2, output)
                self.assertEqual([line for line in records if line.startswith('server ')],
                                 ['server 1 original', 'server 1 updated'], output)
            finally:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
