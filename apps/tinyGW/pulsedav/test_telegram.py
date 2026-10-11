"""Offline coverage for optional Telegram delivery and WebDAV integration."""
import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pulsedav as dav


class TelegramTests(unittest.TestCase):
    def test_disabled_does_not_run_command(self):
        with patch.object(dav.subprocess, 'run') as run:
            self.assertEqual(dav.send_telegram_report({}, 'report', 'pulse.md')['status'], 'disabled')
            run.assert_not_called()

    def test_file_content_config_and_cleanup(self):
        paths = []
        def run(command, **kwargs):
            self.assertEqual(command[:3], ['/opt/bin/telegram-send', '--config', str(dav.APP_DIR / 'bot.conf')])
            path = Path(command[-1])
            paths.append(path)
            self.assertEqual(path.read_text(), '# 상태\n' + 'x' * 5000)
            self.assertEqual(kwargs['timeout'], 12)
            self.assertEqual(command[command.index('--caption') + 1],
                             '🖥️ Host: gw\n🏠 Local IP: 192.168.1.2\n🌐 Public IP: 203.0.113.1')
            return Mock(returncode=0)
        settings = {'telegram': {'enabled': True, 'executable': '/opt/bin/telegram-send',
                                 'config_path': 'bot.conf', 'timeout_seconds': 12}}
        with patch.object(dav.subprocess, 'run', side_effect=run):
            result = dav.send_telegram_report(settings, '# 상태\n' + 'x' * 5000, 'pulse.md',
                {'hostname': 'gw', 'network': {'internal_ip': '192.168.1.2', 'public_ip': '203.0.113.1'}})
        self.assertEqual(result['status'], 'sent')
        self.assertFalse(paths[0].exists())

    def test_failures_are_nonfatal(self):
        for failure in (FileNotFoundError(), subprocess.TimeoutExpired('telegram-send', 1)):
            with self.subTest(failure=failure), patch.object(dav.subprocess, 'run', side_effect=failure):
                self.assertEqual(dav.send_telegram_report({'telegram': {'enabled': True}}, 'report', 'pulse.md')['status'], 'failed')
        with patch.object(dav.subprocess, 'run', return_value=Mock(returncode=1)):
            self.assertEqual(dav.send_telegram_report({'telegram': {'enabled': True}}, 'report', 'pulse.md')['status'], 'failed')

    def test_both_report_types_upload_and_send_once_for_multiple_targets(self):
        for sender in (dav.send_once, dav.send_iptime_list):
            with self.subTest(sender=sender.__name__), \
                 patch.object(dav, 'validate_settings', return_value=[]), \
                 patch.object(dav, 'load_state', return_value={}), \
                 patch.object(dav, 'save_state'), \
                 patch.object(dav, 'boot_marker', return_value='boot'), \
                 patch.object(dav, 'collect_snapshot', return_value={'uptime_minutes': 5}), \
                 patch.object(dav, 'format_markdown', return_value='report'), \
                 patch.object(dav, 'get_iptime_report', return_value='iptime'), \
                 patch.object(dav, 'format_iptime_markdown', return_value='report'), \
                 patch.object(dav, 'build_host_remote_dirs', return_value=['host/a', 'host/b']), \
                 patch.object(dav, 'upload_remote_file', return_value=[]) as upload, \
                 patch.object(dav, 'prune_old_remote_files', return_value=[]), \
                 patch.object(dav, 'send_telegram_report', return_value={'status': 'failed'}) as telegram:
                result = sender(dav.default_settings())
                self.assertEqual(upload.call_count, 2)
                expected = [unittest.mock.ANY, 'report', result['file_name']]
                if sender is dav.send_once:
                    expected.append(unittest.mock.ANY)
                telegram.assert_called_once_with(*expected)
                self.assertEqual(result['telegram']['status'], 'failed')
                self.assertEqual(len(result['remote_paths']), 2)


if __name__ == '__main__':
    unittest.main()
