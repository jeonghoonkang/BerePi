"""Docker service orchestration without downloading maps or requiring a daemon."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parent / 'nominatim'
SPEC = importlib.util.spec_from_file_location('nominatim_docker', SOURCE / 'docker_service.py')
service = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(service)


class DockerServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name).resolve()
        (self.directory / '.env.example').write_bytes((SOURCE / '.env.example').read_bytes())
        self.output = io.StringIO()
        redirect = contextlib.redirect_stdout(self.output)
        redirect.__enter__()
        self.addCleanup(redirect.__exit__, None, None, None)

    def initialize(self):
        self.assertEqual(service.main(['init'], self.directory), 0)

    def test_init_private_random_secret_and_no_overwrite(self):
        self.initialize()
        config = self.directory / '.env'
        original = config.read_text()
        password = next(line.split('=', 1)[1] for line in original.splitlines()
                        if line.startswith('NOMINATIM_PASSWORD='))
        self.assertEqual(len(password), 64)
        self.assertEqual(stat.S_IMODE(config.stat().st_mode), 0o600)
        self.assertNotIn(password, self.output.getvalue())
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(service.main(['init'], self.directory), 1)
        self.assertEqual(config.read_text(), original)

    def test_missing_config_does_not_start_docker(self):
        with patch.object(service.subprocess, 'run') as run, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(service.main(['up'], self.directory), 1)
        run.assert_not_called()

    def test_missing_docker(self):
        self.initialize()
        with patch.object(service.shutil, 'which', return_value=None), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(service.main(['up'], self.directory), 1)

    def test_lifecycle_uses_absolute_paths_and_preserves_volume(self):
        self.initialize()
        for action, expected in [('up', ['up', '-d']), ('stop', ['stop']),
                                 ('down', ['down']), ('restart', ['restart']),
                                 ('status', ['ps', '--all'])]:
            with self.subTest(action=action), patch.object(service.shutil, 'which', return_value='/bin/docker'), \
                    patch.object(service.subprocess, 'run') as run:
                self.assertEqual(service.main([action], self.directory), 0)
                prefix = ['docker', 'compose', '--project-directory', str(self.directory),
                          '--env-file', str(self.directory / '.env'), '-f',
                          str(self.directory / 'compose.yaml')]
                self.assertEqual(run.call_args_list[0].args[0], prefix + ['config', '--quiet'])
                self.assertEqual(run.call_args_list[1].args[0], prefix + expected)
                self.assertNotIn('--volumes', run.call_args_list[1].args[0])

    def check(self, payload):
        config = {'services': {'nominatim': {'ports': [
            {'target': 8080, 'published': '8181', 'host_ip': '0.0.0.0'}]}}}
        response = io.StringIO(json.dumps(payload))
        with patch.object(service.subprocess, 'run', return_value=subprocess.CompletedProcess(
                [], 0, stdout=json.dumps(config))), \
                patch.object(service, 'urlopen', return_value=response) as request:
            service.check_service(['docker', 'compose'])
        request.assert_called_once_with('http://127.0.0.1:8181/status?format=json', timeout=10)

    def test_ready_requires_usable_database(self):
        self.check({'status': 0})
        self.assertIn('지도 DB 준비 완료', self.output.getvalue())

    def test_http_success_alone_is_not_ready(self):
        for payload in ({'status': 700}, {}, []):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.check(payload)

    def test_compose_failure_does_not_print_captured_secrets(self):
        self.initialize()
        failure = subprocess.CalledProcessError(1, ['docker'], output='secret', stderr='secret')
        errors = io.StringIO()
        with patch.object(service.shutil, 'which', return_value='/bin/docker'), \
                patch.object(service.subprocess, 'run', side_effect=failure), \
                contextlib.redirect_stderr(errors):
            self.assertEqual(service.main(['check'], self.directory), 1)
        self.assertNotIn('secret', errors.getvalue())


if __name__ == '__main__':
    unittest.main()
