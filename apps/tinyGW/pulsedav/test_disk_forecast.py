import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pulsedav as dav


class DiskForecastTests(unittest.TestCase):
    def forecast(self, used, initial=None, output=None, alerts=None):
        used *= 100000
        if initial is not None:
            initial *= 100000
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'history.json'
            key = json.dumps(['/dev/sda1', '/'], ensure_ascii=False)
            if initial is not None:
                path.write_text(json.dumps({key: [{
                    'at': (datetime.now(dav.SEOUL) - timedelta(days=10)).isoformat(),
                    'used_kib': initial, 'capacity_kib': 100000000,
                }]}))
            data = output if output is not None else f'Filesystem 1024-blocks Used Available Capacity Mounted on\n/dev/sda1 100000000 {used} {100000000-used} 90% /\n'
            with patch.object(dav, 'DISK_HISTORY_PATH', path), \
                 patch.object(dav, 'APP_DIR', Path(directory)), \
                 patch.object(dav, 'run_command', return_value=data):
                text = dav.get_disk_forecast(alerts)
            return text, json.loads(path.read_text()) if path.exists() else {}

    def test_growth_predicts_ten_days(self):
        text, history = self.forecast(900, 800)
        self.assertIn('약 10.0일 후 100% 예상', text)
        self.assertIn('평균 증가', text)
        self.assertEqual(len(next(iter(history.values()))), 2)

    def test_minimum_disk_size_boundary(self):
        threshold = (dav.MIN_DISK_BYTES + 1023) // 1024
        for total, expected in [(threshold - 1, 0), (threshold, 1)]:
            with self.subTest(total=total):
                output = f'Filesystem blocks Used Available Capacity Mounted on\n/dev/sda1 {total} {total} 0 100% /\n'
                alerts = []
                _, history = self.forecast(0, output=output, alerts=alerts)
                self.assertEqual(len(alerts), expected)
                self.assertEqual(len(history), expected)
                with patch.object(dav, 'run_command', return_value=output):
                    usage = dav.get_disk_usage()
                self.assertEqual('/dev/sda1' in usage, bool(expected))

    def test_telegram_alert_requires_strictly_more_than_95_percent(self):
        for used, expected in [(900, 0), (950, 0), (951, 1), (1000, 1)]:
            with self.subTest(used=used):
                alerts = []
                self.forecast(used, alerts=alerts)
                self.assertEqual(len(alerts), expected)

    def test_thresholds_and_reset(self):
        text, history = self.forecast(800)
        self.assertIn('이력 기록 중', text)
        self.assertTrue(history)
        text, history = self.forecast(799, 850)
        self.assertIn('80% 미만', text)
        self.assertEqual(history, {})
        self.assertIn('이력 부족', self.forecast(900)[0])

    def test_flat_declining_and_full(self):
        for initial in (900, 950):
            self.assertIn('증가 추세 없음', self.forecast(900, initial)[0])
        self.assertIn('100% 도달', self.forecast(1000)[0])

    def test_unavailable_does_not_erase_history(self):
        text, history = self.forecast(900, 800, output='')
        self.assertIn('조회 실패', text)
        self.assertTrue(history)


if __name__ == '__main__':
    unittest.main()
