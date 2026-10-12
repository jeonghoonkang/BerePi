import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import check_tinyGW_all as check


def report(stamp, rows):
    return f'- 호스트명: host\n- 내부 IP: 192.168.1.2\n- 생성 시각: {stamp} KST\n## HDD 공간\n```text\n{rows}\n```\n'


class AggregateTests(unittest.TestCase):
    def test_latest_and_size_filter(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'old.md').write_text(report('2026-10-12 10:00:00', 'Filesystem Size(GiB) Used Available Use% Mounted on\n/dev/old 200 100 100 50% /'))
            (root / 'new.md').write_text(report('2026-10-13 10:00:00', 'Filesystem Size(GiB) Used Available Use% Mounted on\n/dev/sda1 200 192 8 96% /\n/dev/boot 1 1 0 100% /boot'))
            (root / 'iptime.md').write_text('# ipTIME report')
            reports, errors = check.collect(root)
            self.assertEqual(len(reports), 1)
            self.assertFalse(errors)
            text = check.render(reports, errors)
            self.assertIn('/dev/sda1 (/): 빈 공간 4%', text)
            self.assertNotIn('/dev/boot', text)
            self.assertNotIn('/dev/old', text)
            self.assertIn('2026-10-13 10:00:00 KST', text)

    def test_legacy_df(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.md'
            path.write_text(report('2026-10-13 10:00:00', 'Filesystem Size Used Avail Capacity Mounted on\n/dev/data 100G 80G 20G 80% /data files\n/dev/small 90G 89G 1G 99% /small'))
            self.assertEqual(check.parse_report(path)['disks'], ['💽 /dev/data (/data files): 빈 공간 20%'])

    def test_text_send_splits(self):
        with patch.object(check.subprocess, 'run', return_value=Mock(returncode=0)) as run:
            check.send_text('x' * 4000, 'telegram-send', '/tmp/bot.conf', 12)
        self.assertEqual(run.call_count, 3)
        self.assertEqual(''.join(c.args[0][-1] for c in run.call_args_list), 'x' * 4000)
        self.assertNotIn('--file', run.call_args.args[0])
