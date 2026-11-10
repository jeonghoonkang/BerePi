import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from version_info import VERSION, log_interval, version_info, version_label, version_logging


class VersionInfoTests(unittest.TestCase):
    def test_git_identity_and_modified_state_are_available(self):
        with patch('version_info.subprocess.run', side_effect=[
                subprocess.CompletedProcess([], 0, 'abc123\n2026-11-11T12:00:00+09:00\n'),
                subprocess.CompletedProcess([], 0, ' M app.py\n')]):
            info = version_info()
        self.assertEqual(info['revision'], 'abc123')
        self.assertTrue(info['modified'])
        self.assertIn('미커밋 변경 포함', version_label(info))

    def test_release_works_without_git(self):
        with patch('version_info.subprocess.run', side_effect=FileNotFoundError):
            info = version_info()
        self.assertEqual(info['version'], VERSION)
        self.assertIsNone(info['revision'])
        self.assertIn('버전 기준일', version_label(info))

    def test_periodic_reporter_stops_on_exit_and_uses_snapshot(self):
        info = {'version': VERSION, 'release_date': '2026-11-11',
                'revision': 'startup', 'committed_at': 'today', 'modified': False}
        repeated = threading.Event()
        class Output(io.StringIO):
            def write(self, text):
                result = super().write(text)
                if '실행 버전:' in text:
                    repeated.set()
                return result
        output = Output()
        with version_logging(info, interval=0.01, stream=output):
            info['revision'] = 'changed-on-disk'
            self.assertTrue(repeated.wait(2), 'No periodic output')
        self.assertIn('KST', output.getvalue())
        self.assertNotIn('changed-on-disk', output.getvalue())
        self.assertFalse(any(t.name == 'photo-browser-version' for t in threading.enumerate()))

    def test_zero_interval_prints_once_and_json_stdout_is_preserved(self):
        from cli import main
        with tempfile.TemporaryDirectory() as folder:
            output, errors = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                code = main(['--db', folder, '--version-log-interval', '0', 'merge-status'])
        self.assertEqual(code, 0)
        self.assertIsInstance(json.loads(output.getvalue()), dict)
        self.assertIn(VERSION, errors.getvalue())
        self.assertEqual(errors.getvalue().count('Photo Browser v'), 1)

    def test_version_command_needs_no_database(self):
        from cli import main
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as result:
            main(['--version'])
        self.assertEqual(result.exception.code, 0)
        self.assertIn(VERSION, output.getvalue())

    def test_invalid_intervals_are_rejected(self):
        import argparse
        for value in ('-1', 'nan', 'inf', 'invalid'):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                log_interval(value)
        self.assertEqual(log_interval('0'), 0)

    def test_version_is_visible_on_login_and_authenticated_pages(self):
        from app import create_app
        from test_support import create_app as authenticated_app
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            app = create_app(root, root, root / 'db')
            response = app.test_client().get('/')
            self.assertEqual(response.status_code, 200)
            self.assertIn(('Photo Browser v' + VERSION).encode(), response.data)
            client = authenticated_app(root, root, root / 'second' / 'db').test_client()
            for route in ('/', '/jobs'):
                response = client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertIn(('Photo Browser v' + VERSION).encode(), response.data)


if __name__ == '__main__':
    unittest.main()
