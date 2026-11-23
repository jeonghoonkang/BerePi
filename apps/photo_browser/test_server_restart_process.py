"""Exercise a real isolated server restart, including Windows exec replacement."""
import base64
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import URLError
from urllib.request import Request, urlopen
from urllib.parse import quote


class ServerRestartProcessTests(unittest.TestCase):
    def test_real_restart_keeps_launch_arguments_environment_and_database(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / 'photos'
            source.mkdir()
            marker = root / 'boots.jsonl'
            wrapper = root / 'start.py'
            wrapper.write_text(
                'import json, os, sys\n'
                f'sys.path.insert(0, {str(Path(__file__).resolve().parent)!r})\n'
                f'with open({str(marker)!r}, "a", encoding="utf-8") as stream:\n'
                '    stream.write(json.dumps({"pid": os.getpid(), "argv": sys.orig_argv, "cwd": os.getcwd(), "marker": os.environ.get("RESTART_PROCESS_TEST")}) + "\\n")\n'
                'from app import main\nmain()\n', encoding='utf-8')
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                port = listener.getsockname()[1]
            origin = f'http://127.0.0.1:{port}'
            environment = {**os.environ, 'PHOTO_BROWSER_PASSWORD': 'restart-process-only', 'RESTART_PROCESS_TEST': 'preserved'}
            command = [sys.executable, '-u', str(wrapper), '--root', str(root), '--directory', str(source),
                       '--db', str(root / 'db'), '--host', '127.0.0.1', '--port', str(port), '--limit', '73',
                       '--source-check-interval', '0', '--version-log-interval', '0']
            auth = 'Basic ' + base64.b64encode(b'test:restart-process-only').decode()
            def request(path, post=False):
                req = Request(origin + path, data=b'{}' if post else None,
                              headers={'Authorization': auth, 'Content-Type': 'application/json', 'X-Photo-Browser': '1'})
                with urlopen(req, timeout=1) as response:
                    return json.load(response)
            def wait_for(predicate):
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    try:
                        state = request('/api/server-lifecycle')
                        if predicate(state):
                            return state
                    except (URLError, OSError, ValueError):
                        pass
                    time.sleep(0.1)
                self.fail('Server restart timed out: ' + (root / 'server.log').read_text(encoding='utf-8', errors='replace')[-3000:])
            with (root / 'server.log').open('w', encoding='utf-8') as log:
                process = subprocess.Popen(command, cwd=root, env=environment, stdout=log, stderr=subprocess.STDOUT)
                latest = None
                try:
                    first = wait_for(lambda state: state['supported'])
                    latest = first
                    (root / 'db' / 'restart-marker.txt').write_text('keep this DB', encoding='utf-8')
                    self.assertTrue(request('/api/server-restart', post=True)['pending'])
                    latest = wait_for(lambda state: state['supported'] and state['instance_id'] != first['instance_id'])
                    boots = [json.loads(line) for line in marker.read_text(encoding='utf-8').splitlines()]
                    self.assertEqual(len(boots), 2)
                    self.assertEqual(boots[0]['argv'], boots[1]['argv'])
                    self.assertEqual(boots[0]['cwd'], boots[1]['cwd'])
                    self.assertEqual(boots[1]['marker'], 'preserved')
                    self.assertEqual((root / 'db' / 'restart-marker.txt').read_text(), 'keep this DB')
                    self.assertEqual(request('/api/browse?path=' + quote(str(source)))['limit'], 73)
                finally:
                    # Kill only the authenticated server process created by this test.
                    try:
                        current = request('/api/server-lifecycle')
                        boots = [json.loads(line) for line in marker.read_text(encoding='utf-8').splitlines()]
                        if current['pid'] == boots[-1]['pid']:
                            os.kill(current['pid'], signal.SIGTERM)
                    except (URLError, OSError, ValueError):
                        if process.poll() is None:
                            process.terminate()
                    process.wait(timeout=10)
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        try:
                            request('/api/server-lifecycle')
                        except (URLError, OSError):
                            break
                        time.sleep(0.1)


if __name__ == '__main__':
    unittest.main()
