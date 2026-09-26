import os
import shlex
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import gateway_watchdog
import pulsedav
import sender
import status_check
from time_utils import SEOUL


class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        instant = cls(2026, 9, 25, 23, 30, tzinfo=timezone.utc)
        return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)


class SeoulTimeTests(unittest.TestCase):
    def test_display_and_gateway_log_cross_utc_date_boundary(self):
        with patch.object(sender, 'datetime', FixedDatetime):
            self.assertEqual(sender.current_time_text(), '2026-09-26 08:30:00 KST')
        with patch.object(gateway_watchdog, 'datetime', FixedDatetime), patch('builtins.print') as output:
            gateway_watchdog.log('test')
            output.assert_called_once_with('[2026-09-26T08:30:00+09:00] test', flush=True)

    def test_webdav_timestamp_preserves_instant(self):
        stamp = status_check.iso_time('Fri, 25 Sep 2026 23:30:00 GMT')
        self.assertEqual(stamp, '2026-09-26T08:30:00+09:00')
        age = (datetime(2026, 9, 26, 9, tzinfo=SEOUL) - datetime.fromisoformat(stamp)).total_seconds()
        self.assertEqual(age, 1800)

    def test_cron_time_command_runs_in_utc_environment(self):
        line = sender.build_crontab_lines(None, None)[0]
        tokens = shlex.split(line)
        code = tokens[tokens.index('-c') + 1]
        result = subprocess.run([sys.executable, '-c', code], cwd=Path(sender.__file__).parent,
                                env={**os.environ, 'TZ': 'UTC'}, capture_output=True, text=True, check=True)
        self.assertTrue(result.stdout.strip().endswith('KST'))

    def test_report_filename_and_saved_timestamp(self):
        settings = pulsedav.default_settings()
        settings['webdav']['hostname'] = 'https://example.test'
        with patch.object(pulsedav, 'datetime', FixedDatetime), patch.object(pulsedav, 'load_state', return_value={}), patch.object(pulsedav, 'boot_marker', return_value='boot'), patch.object(pulsedav, 'collect_snapshot', return_value={'uptime_minutes': 10}), patch.object(pulsedav, 'format_markdown', return_value='report'), patch.object(pulsedav, 'upload_remote_file'), patch.object(pulsedav, 'prune_old_remote_files', return_value=[]), patch.object(pulsedav, 'save_state') as save, patch('builtins.print'):
            result = pulsedav.send_once(settings)
        self.assertEqual(result['file_name'], 'pulse_20260926_083000.md')
        self.assertEqual(save.call_args.args[0]['last_sent_at'], '2026-09-26T08:30:00+09:00')


if __name__ == '__main__':
    unittest.main()
