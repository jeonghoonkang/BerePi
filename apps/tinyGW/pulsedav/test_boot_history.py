import subprocess
import unittest
from unittest.mock import patch

import pulsedav
import test_uptime_display


class BootHistoryTests(unittest.TestCase):
    def test_last_records_are_converted_to_seoul_and_footer_ignored(self):
        output = '\n'.join([
            'reboot system boot 6.8 2026-10-29T01:00:00+00:00 still running',
            'reboot system boot 6.8 2026-10-28T01:00:00+00:00 - ...',
            'reboot system boot 6.8 2026-10-27T01:00:00+00:00 - ...',
            'wtmp begins 2026-01-01T00:00:00+00:00',
        ])
        with patch.object(pulsedav.subprocess, 'run', return_value=
                          subprocess.CompletedProcess([], 0, output)):
            self.assertEqual(pulsedav.recent_boot_times(), [
                '2026-10-29 10:00:00 KST', '2026-10-28 10:00:00 KST',
                '2026-10-27 10:00:00 KST',
            ])

    def test_unavailable_history_does_not_break_report(self):
        for failure in [FileNotFoundError(), subprocess.TimeoutExpired('last', 10)]:
            with self.subTest(failure=failure), patch.object(
                    pulsedav.subprocess, 'run', side_effect=failure):
                self.assertEqual(pulsedav.recent_boot_times(), [])
        for code, output in [(0, ''), (1, 'error'), (0, 'reboot malformed')]:
            with patch.object(pulsedav.subprocess, 'run', return_value=
                              subprocess.CompletedProcess([], code, output)):
                self.assertEqual(pulsedav.recent_boot_times(), [])
        self.assertIn('uptime 기반 추정', test_uptime_display.UptimeDisplayTests().report(60))

    def test_report_shows_history(self):
        settings = pulsedav.default_settings()
        settings['include'] = {}
        snapshot = {
            'collected_at': '2026-10-29 12:00:00 KST',
            'hostname': 'test', 'os': 'Linux', 'uptime_minutes': 120,
            'recent_boot_times': ['2026-10-29 10:00:00 KST',
                                  '2026-10-28 10:00:00 KST'],
            'network': dict.fromkeys(
                ['internal_ip', 'public_ip', 'gateway', 'ddns_name', 'ssh_port'], ''),
        }
        report = pulsedav.format_markdown(settings, snapshot, False)
        for boot in snapshot['recent_boot_times']:
            self.assertIn('  - ' + boot, report)
        self.assertNotIn('과거 부팅 기록 확인 불가', report)


if __name__ == '__main__':
    unittest.main()
