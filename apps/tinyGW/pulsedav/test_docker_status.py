import subprocess
import unittest
from unittest.mock import patch

from pulsedav import get_docker_status


class DockerStatusTests(unittest.TestCase):
    def test_permission_error_not_hidden_by_partial_stdout(self):
        response = subprocess.CompletedProcess([], 1, 'Server  /\n', 'permission denied while trying to connect to the Docker daemon socket')
        with patch('pulsedav.subprocess.run', return_value=response) as run:
            report = get_docker_status()
        self.assertIn('접근 권한이 없습니다', report)
        self.assertNotIn('Server  /', report)
        self.assertEqual(run.call_count, 1)

    def test_successful_info_does_not_hide_ps_failure(self):
        with patch('pulsedav.subprocess.run', side_effect=[subprocess.CompletedProcess([], 0, 'Server 27 / Linux', ''), subprocess.CompletedProcess([], 1, '', 'permission denied')]):
            self.assertIn('상태는 확인하지 못했습니다', get_docker_status())

    def test_success_includes_container_rows(self):
        with patch('pulsedav.subprocess.run', side_effect=[subprocess.CompletedProcess([], 0, 'Server 27 / Linux', ''), subprocess.CompletedProcess([], 0, 'NAMES STATUS PORTS\napp Up 2 hours 8080', '')]):
            self.assertEqual(get_docker_status(), 'Server 27 / Linux\n\nNAMES STATUS PORTS\napp Up 2 hours 8080')

    def test_missing_cli_timeout_and_daemon_unavailable(self):
        for failure, expected in [(FileNotFoundError(), 'PATH'), (subprocess.TimeoutExpired('docker', 20), '시간이 초과')]:
            with self.subTest(failure=failure), patch('pulsedav.subprocess.run', side_effect=failure):
                self.assertIn(expected, get_docker_status())
        with patch('pulsedav.subprocess.run', return_value=subprocess.CompletedProcess([], 1, '', 'Cannot connect to the Docker daemon')):
            self.assertIn('daemon에 연결할 수 없습니다', get_docker_status())


if __name__ == '__main__':
    unittest.main()
