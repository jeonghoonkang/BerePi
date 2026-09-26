import subprocess
from contextlib import ExitStack
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pulsedav import get_docker_status, warn_docker_group_membership


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


class DockerGroupWarningTests(unittest.TestCase):
    def check_warning(self, active=(), configured=(100,), missing=False):
        with ExitStack() as stack:
            for target, value in {
                'pulsedav.platform.system': 'Linux',
                'pulsedav.os.geteuid': 1000,
                'pulsedav.os.getegid': 100,
                'pulsedav.os.getgroups': list(active),
                'pulsedav.os.getgrouplist': list(configured),
                'pwd.getpwuid': SimpleNamespace(pw_name='real-user', pw_gid=100),
            }.items():
                stack.enter_context(patch(target, return_value=value))
            stack.enter_context(patch('grp.getgrnam', side_effect=KeyError('docker') if missing else None,
                                      return_value=SimpleNamespace(gr_gid=999)))
            output = stack.enter_context(patch('pulsedav.sys.stderr'))
            stack.enter_context(patch('pulsedav.subprocess.run', side_effect=AssertionError('no commands permitted')))
            warn_docker_group_membership()
            return ''.join(call.args[0] for call in output.write.call_args_list)

    def test_nonmember_warns_with_actual_account(self):
        report = self.check_warning()
        self.assertIn('WARNING:', report)
        self.assertIn('sudo usermod -aG docker real-user', report)
        self.assertIn('root 수준', report)

    def test_active_member_does_not_warn(self):
        self.assertEqual(self.check_warning(active=[999]), '')

    def test_membership_pending_login(self):
        report = self.check_warning(configured=[100, 999])
        self.assertIn('현재 프로세스에는 적용되지 않았습니다', report)
        self.assertNotIn('usermod', report)

    def test_missing_group_warns(self):
        self.assertIn('docker 그룹이 없습니다', self.check_warning(missing=True))

    def test_root_and_other_platform_skip(self):
        for system, uid in [('Linux', 0), ('Darwin', 1000), ('Windows', 1000)]:
            with self.subTest(system=system), patch('pulsedav.platform.system', return_value=system), patch('pulsedav.os.geteuid', return_value=uid), patch('pulsedav.sys.stderr') as output:
                warn_docker_group_membership()
                output.write.assert_not_called()

    def test_cli_warning_does_not_block_status_check(self):
        import sender
        with patch('sys.argv', ['sender.py', '--check-status', '--config', 'test.json']), patch.object(sender, 'warn_docker_group_membership') as warning, patch('status_check.check_status', return_value=0) as check:
            self.assertEqual(sender.main(), 0)
            warning.assert_called_once_with()
            check.assert_called_once()


if __name__ == '__main__':
    unittest.main()
