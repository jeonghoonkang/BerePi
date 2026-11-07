import contextlib
import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from nominatim_service import _validate_command

SERVICE = Path(__file__).with_name('nominatim') / 'server.py'
spec = importlib.util.spec_from_file_location('photo_browser_local_nominatim', SERVICE)
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class LocalNominatimTests(unittest.TestCase):
    def test_serve_starts_official_engine_in_foreground_with_project(self):
        factory, run = Mock(), Mock()
        with tempfile.TemporaryDirectory() as folder, patch.object(server, 'load_runtime', return_value=(factory, run)), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(server.main(['serve', '--project-dir', folder, '--server', '127.0.0.1:8080']), 0)
            factory.assert_called_once_with(Path(folder).resolve())
            run.assert_called_once_with(factory.return_value, host='127.0.0.1', port=8080,
                                        workers=1, reload=False, log_level='info', timeout_graceful_shutdown=3)

    def test_missing_project_or_dependencies_reports_error_without_running(self):
        for folder, error in (('/not-existing-nominatim-project', '프로젝트 디렉토리'),):
            output = io.StringIO()
            with patch.object(server, 'load_runtime') as runtime, contextlib.redirect_stderr(output), self.assertRaises(SystemExit) as raised:
                server.main(['serve', '--project-dir', folder])
            self.assertEqual(raised.exception.code, 2)
            self.assertIn(error, output.getvalue())
            runtime.assert_not_called()
        with tempfile.TemporaryDirectory() as folder:
            output = io.StringIO()
            with patch.object(server, 'load_runtime', side_effect=ModuleNotFoundError('nominatim_api')), contextlib.redirect_stderr(output), self.assertRaises(SystemExit) as raised:
                server.main(['serve', '--project-dir', folder])
            self.assertEqual(raised.exception.code, 2)
            self.assertIn('pip install -r', output.getvalue())

    def test_invalid_address_does_not_start_runtime(self):
        for address in ('127.0.0.1', '127.0.0.1:0', '127.0.0.1:70000', 'host:notaport', 'host:8080/path'):
            with self.subTest(address=address), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                server.main(['serve', '--project-dir', '.', '--server', address])
        self.assertEqual(server.server_address('[::1]:8080'), ('::1', 8080))

    def test_missing_system_command_selects_local_service_without_shell(self):
        with tempfile.TemporaryDirectory() as folder, patch('nominatim_service.shutil.which', return_value=None):
            argv = _validate_command(['nominatim', 'serve', '--project-dir', folder, '--server', '127.0.0.1:8080'])
        self.assertEqual(argv[:3], [sys.executable, str(SERVICE), 'serve'])

    def test_local_executable_accepts_requested_command_help(self):
        result = subprocess.run([sys.executable, str(SERVICE.with_name('nominatim')), 'serve', '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--project-dir', result.stdout)
        self.assertIn('--server', result.stdout)


if __name__ == '__main__':
    unittest.main()
