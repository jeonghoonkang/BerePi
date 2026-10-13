"""Read-only quota diagnostics and CLI routing regressions."""
import unittest
from unittest.mock import patch

import pulsedav as dav
import sender


class DryRunTests(unittest.TestCase):
    def test_cli_routes_before_any_send_or_docker_check(self):
        with patch('sys.argv', ['sender.py', '--config', 'this.setting.json', '--once', '--dry-run']), \
             patch.object(sender, 'load_settings', return_value={'test': True}) as load, \
             patch.object(sender, 'dry_run_remote_quota', return_value=1) as probe, \
             patch.object(sender, 'send_once') as send, \
             patch.object(sender, 'warn_docker_group_membership') as warn:
            self.assertEqual(sender.main(), 1)
        load.assert_called_once_with('this.setting.json')
        probe.assert_called_once_with({'test': True})
        send.assert_not_called()
        warn.assert_not_called()

    def test_rejects_mutating_modes(self):
        for mode in ('--loop', '--install-crontab', '--test-telegram-disk', '--iptime-list'):
            with self.subTest(mode=mode), patch('sys.argv', ['sender.py', '--dry-run', mode]), \
                 patch('sys.stderr'):
                with self.assertRaises(SystemExit) as error:
                    sender.parse_args()
                self.assertEqual(error.exception.code, 2)

    def test_all_targets_checked_after_quota_failure_without_writes(self):
        config = dav.WebDAVConfig('https://example.test', '/dav/user', 'user', 'secret')
        with patch.object(dav, 'validate_settings', return_value=[]), \
             patch.object(dav, 'build_webdav_config', return_value=config), \
             patch.object(dav, 'build_host_remote_dirs', return_value=['tinyGW/a', 'tinyGW/b']), \
             patch.object(dav, 'get_remote_available_bytes', side_effect=[dav.WebDAVStorageError('unknown'), 0]) as quota, \
             patch.object(dav, 'upload_remote_file') as upload, \
             patch.object(dav, 'delete_remote_path') as delete, \
             patch.object(dav, 'ensure_remote_directories') as mkdir, \
             patch.object(dav, 'save_state') as save, patch('builtins.print'):
            self.assertEqual(dav.dry_run_remote_quota({}), 1)
        self.assertEqual(quota.call_count, 2)
        quota.assert_called_with(config, 'tinyGW/b', verbose=True)
        for operation in (upload, delete, mkdir, save):
            operation.assert_not_called()

    def test_zero_quota_is_successful_query(self):
        with patch.object(dav, 'validate_settings', return_value=[]), \
             patch.object(dav, 'build_webdav_config'), \
             patch.object(dav, 'build_host_remote_dirs', return_value=['tinyGW/a']), \
             patch.object(dav, 'get_remote_available_bytes', return_value=0), patch('builtins.print'):
            self.assertEqual(dav.dry_run_remote_quota({}), 0)


if __name__ == '__main__':
    unittest.main()
