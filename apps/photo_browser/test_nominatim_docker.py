import contextlib
import io
import http.client
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app import main
from nominatim_docker import (CONFIG, DEFAULT_IMAGE, DEFAULT_PBF, MANAGED, PORT,
                              _healthy, managed_nominatim_docker, settings)

# Simulates the Docker CLI and a daemon-owned HTTP process, not a real Nominatim DB.
FAKE_DOCKER = r'''
import json, os, signal, subprocess, sys
from pathlib import Path
root = Path(os.environ['PHOTO_DOCKER_TEST_DIR'])
args = sys.argv[1:]
with (root / 'commands.log').open('a') as out: out.write(json.dumps(args) + '\n')
container_file, volume_file = root / 'container.json', root / 'volume.json'
def read(path): return json.loads(path.read_text()) if path.exists() else None
def write(path, data): path.write_text(json.dumps(data))
def labels():
    return dict(args[i+1].split('=', 1) for i, value in enumerate(args) if value == '--label')
c, v = read(container_file), read(volume_file)
if args[0] == 'info': pass
elif args[:2] == ['image', 'inspect']: print('[]')
elif args[:2] == ['volume', 'ls']:
    if v: print(v['Name'])
elif args[:2] == ['volume', 'inspect']: print(json.dumps([v]))
elif args[:2] == ['volume', 'create']:
    write(volume_file, {'Name': args[-1], 'Labels': labels()})
elif args[:2] == ['container', 'ls']:
    if c and ('-a' in args or c['State']['Running']): print(c['Name'])
elif args[:2] == ['container', 'inspect']: print(json.dumps([c]))
elif args[0] == 'create':
    if c: sys.exit(1)
    name = args[args.index('--name')+1]
    write(container_file, {'Name': name, 'Id': name, 'Config': {'Labels': labels()},
                          'State': {'Running': False, 'Status': 'created'},
                          'port': int(args[args.index('--publish')+1].split(':')[1])})
elif args[0] == 'start':
    code = "from http.server import HTTPServer,BaseHTTPRequestHandler\nclass H(BaseHTTPRequestHandler):\n def do_GET(self):\n  self.send_response(200);self.end_headers();self.wfile.write(b'{\"status\":0}')\nHTTPServer(('127.0.0.1',int(__import__('sys').argv[1])),H).serve_forever()"
    if os.environ.get('PHOTO_DOCKER_TEST_UNHEALTHY'): code = code.replace('"status":0', '"status":700')
    service = subprocess.Popen([sys.executable, '-c', code, str(c['port'])],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, start_new_session=True)
    c['pid'] = service.pid
    c['State'] = {'Running': True, 'Status': 'running'}
    write(container_file, c)
elif args[0] == 'stop':
    try: os.kill(c['pid'], signal.SIGTERM)
    except ProcessLookupError: pass
    c['State'] = {'Running': False, 'Status': 'exited'}
    write(container_file, c)
elif args[0] == 'rm':
    if c and c['State']['Running']:
        try: os.kill(c['pid'], signal.SIGKILL)
        except ProcessLookupError: pass
    container_file.unlink(missing_ok=True)
elif args[0] == 'logs': pass
else: sys.exit(2)
'''


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


def serving(port):
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=.3)
    try:
        connection.request('GET', '/')
        response = connection.getresponse()
        response.read()
        return response.status in {200, 302, 401}
    except (OSError, http.client.HTTPException):
        return False
    finally:
        connection.close()


@unittest.skipUnless(os.name == 'posix', 'Watchdog requires POSIX pipes')
class DockerLifecycleTests(unittest.TestCase):
    def check_shutdown(self, stop_signal):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            docker = root / 'docker'
            docker.write_text('#!' + sys.executable + '\n' + FAKE_DOCKER)
            docker.chmod(0o700)
            app_port, service_port = free_port(), free_port()
            while app_port == service_port:
                service_port = free_port()
            env = {**os.environ, 'PATH': str(root) + os.pathsep + os.environ.get('PATH', ''),
                   'PHOTO_DOCKER_TEST_DIR': str(root)}
            env.pop('PHOTO_BROWSER_REVERSE_GEOCODER_URL', None)
            if stop_signal is None:
                env['PHOTO_DOCKER_TEST_UNHEALTHY'] = '1'
            with (root / 'startup.log').open('wb') as log:
                app = subprocess.Popen([sys.executable, str(Path(__file__).with_name('app.py')),
                                        '--root', str(root), '--db', str(root / 'db'), '--port', str(app_port),
                                        '--nominatim-docker', '--nominatim-port', str(service_port),
                                        '--nominatim-ready-timeout', '1' if stop_signal is None else '10'], env=env, stdout=log, stderr=log)
                try:
                    deadline = time.monotonic() + 12
                    while not serving(app_port) and app.poll() is None and time.monotonic() < deadline:
                        time.sleep(.05)
                    if stop_signal is None:
                        app.wait(timeout=10)
                        self.assertEqual(app.returncode, 2, (root / 'startup.log').read_text())
                        self.assertFalse(listening(app_port))
                    else:
                        self.assertTrue(serving(app_port), (root / 'startup.log').read_text())
                        self.assertTrue(listening(service_port))
                        app.send_signal(stop_signal)
                        app.wait(timeout=10)
                    deadline = time.monotonic() + 12
                    while ((root / 'container.json').exists() or listening(service_port)) and time.monotonic() < deadline:
                        time.sleep(.05)
                    self.assertFalse((root / 'container.json').exists(), (root / 'startup.log').read_text())
                    self.assertFalse(listening(service_port))
                    self.assertTrue((root / 'volume.json').exists())
                    commands = [json.loads(line) for line in (root / 'commands.log').read_text().splitlines()]
                    create = next(command for command in commands if command[0] == 'create')
                    self.assertIn(f'127.0.0.1:{service_port}:8080', create)
                    self.assertIn('REVERSE_ONLY=true', create)
                    self.assertIn('PBF_URL=' + DEFAULT_PBF, create)
                    self.assertTrue(any(command[0] == 'stop' for command in commands))
                    self.assertFalse(any(command[:2] == ['volume', 'rm'] for command in commands))
                finally:
                    if app.poll() is None:
                        app.kill(); app.wait(timeout=5)
                    file = root / 'container.json'
                    if file.exists():
                        record = json.loads(file.read_text())
                        if record.get('pid'):
                            try: os.kill(record['pid'], signal.SIGKILL)
                            except ProcessLookupError: pass

    def test_normal_exit_stops_container_and_preserves_volume(self):
        self.check_shutdown(signal.SIGINT)

    def test_force_killed_main_stops_daemon_owned_container(self):
        self.check_shutdown(signal.SIGKILL)

    def test_startup_timeout_cleans_container_and_preserves_volume(self):
        self.check_shutdown(None)


class DockerValidationTests(unittest.TestCase):
    def test_old_software_command_argument_is_removed(self):
        with patch('app.faulthandler.enable'), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            main(['--nominatim-command', 'nominatim serve'])
        self.assertEqual(raised.exception.code, 2)

    def test_docker_missing_and_invalid_volume_fail_before_launch(self):
        with patch('nominatim_docker.shutil.which', return_value=None), self.assertRaisesRegex(ValueError, 'Docker 실행 파일'):
            with managed_nominatim_docker(True): pass
        for volume in ('/host/path', '../data', '-bad'):
            with self.subTest(volume=volume), self.assertRaises(ValueError):
                settings(DEFAULT_IMAGE, DEFAULT_PBF, volume, 8080)

    def test_existing_foreign_volume_is_not_reused_or_removed(self):
        with patch('nominatim_docker.shutil.which', return_value='/usr/bin/docker'), patch('nominatim_docker.Docker') as client:
            client.return_value.run.return_value = subprocess.CompletedProcess([], 0, '', '')
            client.return_value.inspect.side_effect = [None, {'Labels': {}}]
            with self.assertRaisesRegex(ValueError, '기존 볼륨'):
                with managed_nominatim_docker(True): pass
            self.assertFalse(any(call.args[:2] == ('volume', 'create') for call in client.return_value.run.call_args_list))

    def test_matching_running_container_is_reused_without_taking_ownership(self):
        config = settings(DEFAULT_IMAGE, DEFAULT_PBF, 'matching-volume', 8080)
        labels = {MANAGED: '1', CONFIG: config['fingerprint'], PORT: '8080'}
        with patch('nominatim_docker.shutil.which', return_value='/usr/bin/docker'), patch('nominatim_docker.Docker') as client, patch('nominatim_docker._wait_ready'), patch('nominatim_docker.subprocess.Popen') as spawn, patch.dict(os.environ, {'PHOTO_BROWSER_REVERSE_GEOCODER_URL': ''}):
            client.return_value.run.return_value = subprocess.CompletedProcess([], 0, '', '')
            client.return_value.inspect.side_effect = [{'Config': {'Labels': labels}, 'State': {'Running': True}}, {'Labels': labels}]
            with managed_nominatim_docker(True, volume='matching-volume'):
                self.assertEqual(os.environ['PHOTO_BROWSER_REVERSE_GEOCODER_URL'], 'http://127.0.0.1:8080/reverse')
            spawn.assert_not_called()
            self.assertFalse(any(call.args[0] in {'stop', 'rm'} for call in client.return_value.run.call_args_list))


if __name__ == '__main__':
    unittest.main()
