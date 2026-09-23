import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from unittest.mock import Mock, patch

import cron_manager
import gateway_watchdog as gw
import sender


class WatchdogTests(unittest.TestCase):
    def simulate(self, probes, dry_run=False):
        now = [0]
        reboot = Mock()
        def sleep(seconds):
            now[0] += seconds
        with contextlib.redirect_stdout(io.StringIO()):
            result = gw.monitor(probe=Mock(side_effect=probes), reboot=reboot,
                                dry_run=dry_run, clock=lambda: now[0], sleep=sleep)
        return result, now[0], reboot

    def test_success_and_recovery_never_reboot(self):
        for failures in (0, 1, 4, 5):
            result, elapsed, reboot = self.simulate([('192.0.2.1', False)] * failures + [('192.0.2.1', True)])
            self.assertEqual(result, 0)
            self.assertEqual(elapsed, failures * 6 * 60)
            reboot.assert_not_called()

    def test_full_thirty_minutes_required(self):
        result, elapsed, reboot = self.simulate([('192.0.2.1', False)] * 6)
        self.assertEqual(elapsed, 1800)
        self.assertEqual(result, 1)
        reboot.assert_called_once_with()

    def test_missing_route_and_dry_run(self):
        result, elapsed, reboot = self.simulate([(None, False)] * 6, dry_run=True)
        self.assertEqual(elapsed, 1800)
        reboot.assert_not_called()

    def test_lowest_metric_gateway_and_no_route(self):
        with patch.object(gw.subprocess, 'run', return_value=Mock(stdout='[{"gateway":"192.0.2.2","metric":200},{"gateway":"192.0.2.1","metric":10}]')):
            self.assertEqual(gw.default_gateway('ip'), '192.0.2.1')
        with patch.object(gw.subprocess, 'run', return_value=Mock(stdout='[]')):
            self.assertIsNone(gw.default_gateway('ip'))

    def test_ping_tool_failure_is_not_network_failure(self):
        with patch.object(gw.subprocess, 'run', return_value=Mock(returncode=2)):
            with self.assertRaises(RuntimeError):
                gw.ping_gateway('ping', '192.0.2.1')
        reboot = Mock()
        with self.assertRaises(OSError):
            gw.monitor(probe=Mock(side_effect=OSError('missing tool')), reboot=reboot)
        reboot.assert_not_called()


class CronTests(unittest.TestCase):
    def test_replace_legacy_duplicates_preserves_other_jobs(self):
        app = PurePosixPath('/opt/Pulse DAV')
        old = "@reboot cd '/opt/Pulse DAV' && python3 sender.py --once\n"
        unrelated = 'MAILTO=admin\n# comment\n0 * * * * /other/task\n'
        watchdog = "0 * * * * cd '/opt/Pulse DAV' && python3 sender.py --gateway-watchdog\n"
        new = ["*/10 * * * * cd '/opt/Pulse DAV' && python3 sender.py --once"]
        result = cron_manager.merge_crontab(unrelated + old * 3 + watchdog, new, app, False)
        self.assertEqual(result, unrelated + watchdog + new[0] + '\n')
        self.assertEqual(cron_manager.merge_crontab(result, new, app, False), result)

    def test_watchdog_only_replaces_its_own_jobs(self):
        app = PurePosixPath('/app')
        report = '@reboot cd /app && python3 sender.py --once\n'
        old = '0 * * * * cd /app && python3 sender.py --gateway-watchdog --gateway-dry-run\n'
        new = ['@reboot cd /app && python3 sender.py --gateway-watchdog', '0 * * * * cd /app && python3 sender.py --gateway-watchdog']
        result = cron_manager.merge_crontab(report + old * 2, new, app, True)
        self.assertEqual(result, report + '\n'.join(new) + '\n')
        self.assertEqual(cron_manager.merge_crontab(result, new, app, True), result)

    def test_watchdog_cron_never_loads_webdav_settings(self):
        with patch.object(sender, 'load_settings', side_effect=AssertionError('unexpected settings')):
            lines = sender.build_crontab_lines(None, None, True, True)
        self.assertTrue(lines[0].startswith('@reboot '))
        self.assertTrue(lines[1].startswith('0 * * * * '))
        self.assertTrue(all('--gateway-dry-run' in line for line in lines))

    @unittest.skipIf(__import__('os').name == 'nt', 'POSIX flock required')
    def test_install_backs_up_and_writes_merged_cron(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory)
            line = f'0 * * * * cd {app} && python3 sender.py --gateway-watchdog'
            old = '# preserved\n' + line + '\n' + line + '\n'
            with patch.object(cron_manager.subprocess, 'run', side_effect=[Mock(returncode=0, stdout=old), Mock(returncode=0)]) as run:
                backup = cron_manager.install_crontab([line], app, True)
                self.assertEqual(backup.read_text(), old)
                self.assertEqual(run.call_args.kwargs['input'], '# preserved\n' + line + '\n')
                self.assertEqual(run.call_args.args[0], ['crontab', '-'])

    @unittest.skipIf(__import__('os').name == 'nt', 'POSIX flock required')
    def test_installer_preserves_old_cron_on_read_failure(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(cron_manager.subprocess, 'run', return_value=Mock(returncode=1, stderr='permission denied')) as run:
            with self.assertRaises(RuntimeError):
                cron_manager.install_crontab([], Path(directory), True)
            run.assert_called_once()


if __name__ == '__main__':
    unittest.main()
