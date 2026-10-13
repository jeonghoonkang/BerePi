import unittest

import pulsedav


class UptimeDisplayTests(unittest.TestCase):
    def report(self, minutes, first=False, reboot=False):
        settings = pulsedav.default_settings()
        settings['include'] = {}
        snapshot = {
            'collected_at': '2026-10-10 12:00:00 KST',
            'hostname': 'test', 'os': 'Linux', 'uptime_minutes': minutes,
            'network': dict.fromkeys(
                ['internal_ip', 'public_ip', 'gateway', 'ddns_name', 'ssh_port'], ''),
        }
        return pulsedav.format_markdown(settings, snapshot, first, reboot)

    def test_long_uptime_crosses_month_boundary(self):
        self.assertIn(
            'up 이후 44456분 (2026-09-09 15:04 KST부터, 30일 20시간 동작중)',
            self.report(44456),
        )

    def test_boot_message_variants_and_duration_boundaries(self):
        for minutes, duration in [(0, '0일 0시간'), (59, '0일 0시간'),
                                  (60, '0일 1시간'), (1440, '1일 0시간')]:
            for first, reboot, prefix in [(False, False, ''),
                                         (True, False, '부팅한 직후 전송, '),
                                         (True, True, 'reboot 시점 전송, ')]:
                with self.subTest(minutes=minutes, first=first, reboot=reboot):
                    report = self.report(minutes, first, reboot)
                    self.assertIn(f'상태 메세지: {prefix}up 이후 {minutes}분', report)
                    self.assertIn(f'{duration} 동작중)', report)


if __name__ == '__main__':
    unittest.main()
