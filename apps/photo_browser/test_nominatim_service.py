import os
import io
import shlex
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from nominatim_service import _healthy, managed_nominatim

APP = Path(__file__).with_name('app.py')


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def listening(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=.2):
            return True
    except OSError:
        return False


@unittest.skipUnless(os.name == 'posix', 'Process groups require POSIX')
class NominatimServiceTests(unittest.TestCase):
    def check_shutdown(self, stop_signal):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            service_port, app_port = free_port(), free_port()
            while service_port == app_port:
                app_port = free_port()
            service = root / 'geocoder.py'
            service.write_text(
                'import os, signal, sys\n'
                'from pathlib import Path\n'
                'from http.server import BaseHTTPRequestHandler, HTTPServer\n'
                'class Handler(BaseHTTPRequestHandler):\n'
                '    def do_GET(self):\n'
                '        self.send_response(200)\n'
                '        self.end_headers()\n'
                '        self.wfile.write(b\'{"status": 0}\')\n'
                'server = HTTPServer(("127.0.0.1", int(sys.argv[1])), Handler)\n'
                'Path(sys.argv[2]).write_text(str(os.getpid()))\n'
                'if len(sys.argv) == 4:\n'
                '    signal.signal(signal.SIGTERM, signal.SIG_IGN)\n'
                '    os.fork()  # Both workers hold the listener and ignore SIGTERM.\n'
                'server.serve_forever()\n',
                encoding='utf-8')
            pid_file = root / 'service.pid'
            command = [sys.executable, str(service), str(service_port), str(pid_file)]
            if stop_signal == signal.SIGKILL:
                command.append('ignore-term')
            env = {**os.environ, 'PHOTO_BROWSER_REVERSE_GEOCODER_URL': f'http://127.0.0.1:{service_port}/reverse'}
            log_path = root / 'startup.log'
            with log_path.open('wb') as log:
                app = subprocess.Popen([sys.executable, str(APP), '--root', str(root),
                                        '--db', str(root / 'db'), '--directory', str(root),
                                        '--port', str(app_port), '--nominatim-command', shlex.join(command)],
                                       env=env, stdout=log, stderr=log)
                try:
                    deadline = time.monotonic() + 10
                    while app.poll() is None and not listening(app_port) and time.monotonic() < deadline:
                        time.sleep(.05)
                    self.assertTrue(listening(app_port), log_path.read_text())
                    self.assertTrue(listening(service_port))
                    app.send_signal(stop_signal)
                    app.wait(timeout=10)
                    deadline = time.monotonic() + 8
                    while listening(service_port) and time.monotonic() < deadline:
                        time.sleep(.05)
                    self.assertFalse(listening(service_port), log_path.read_text())
                finally:
                    if app.poll() is None:
                        app.kill()
                        app.wait(timeout=5)
                    if pid_file.exists() and listening(service_port):
                        os.killpg(int(pid_file.read_text()), signal.SIGKILL)

    def test_normal_interrupt_stops_owned_service(self):
        self.check_shutdown(signal.SIGINT)

    def test_force_killed_parent_stops_service_even_if_term_is_ignored(self):
        self.check_shutdown(signal.SIGKILL)

    def test_occupied_port_does_not_launch_or_stop_existing_service(self):
        with socket.socket() as existing:
            existing.bind(('127.0.0.1', 0))
            existing.listen()
            port = existing.getsockname()[1]
            with patch.dict(os.environ, {'PHOTO_BROWSER_REVERSE_GEOCODER_URL': f'http://127.0.0.1:{port}/reverse'}):
                with patch('nominatim_service.subprocess.Popen') as spawn, self.assertRaisesRegex(ValueError, '이미 사용 중'):
                    with managed_nominatim('nominatim serve'):
                        self.fail('The existing listener must not be adopted')
                spawn.assert_not_called()
            self.assertTrue(listening(port))

    def test_healthy_existing_server_is_reused_without_needing_an_executable(self):
        with socket.socket() as existing:
            existing.bind(('127.0.0.1', 0))
            existing.listen()
            endpoint = f'http://127.0.0.1:{existing.getsockname()[1]}/reverse'
            with patch.dict(os.environ, {'PHOTO_BROWSER_REVERSE_GEOCODER_URL': endpoint}), patch(
                    'nominatim_service._healthy', return_value=True) as health, patch(
                    'nominatim_service.subprocess.Popen') as spawn:
                with managed_nominatim('not-installed-nominatim serve'):
                    self.assertEqual(os.environ['PHOTO_BROWSER_REVERSE_GEOCODER_URL'], endpoint)
                health.assert_called_once_with(endpoint.replace('/reverse', '/status?format=json'), .5)
                spawn.assert_not_called()
                self.assertTrue(listening(existing.getsockname()[1]))

    def test_missing_executable_and_project_are_rejected_before_launch(self):
        endpoint = f'http://127.0.0.1:{free_port()}/reverse'
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                'PHOTO_BROWSER_REVERSE_GEOCODER_URL': endpoint}), patch('nominatim_service.subprocess.Popen') as spawn:
            commands = [('not-installed-nominatim serve', '실행 파일'),
                        (shlex.join([sys.executable, '--project-dir', directory + '/missing']), '프로젝트 디렉토리'),
                        (shlex.join([sys.executable, '--project-dir']), '프로젝트 경로')]
            for command, message in commands:
                with self.subTest(command=command), self.assertRaisesRegex(ValueError, message):
                    with managed_nominatim(command):
                        self.fail('The invalid command must not be launched')
            spawn.assert_not_called()

    def test_health_check_requires_a_successful_database_status(self):
        for data, expected in ((b'{"status":0}', True), (b'{"status":700}', False),
                               (b'{"status":false}', False), (b'not json', False)):
            with self.subTest(data=data), patch('nominatim_service.build_opener') as opener:
                opener.return_value.open.return_value = io.BytesIO(data)
                self.assertEqual(_healthy('http://127.0.0.1:8080/status?format=json', .5), expected)
