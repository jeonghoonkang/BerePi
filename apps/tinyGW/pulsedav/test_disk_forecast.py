import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pulsedav as dav


class DiskForecastTests(unittest.TestCase):
    def forecast(self, used, initial=None, output=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'history.json'
            key = json.dumps(['/dev/sda1', '/'], ensure_ascii=False)
            if initial is not None:
                path.write_text(json.dumps({key: [{
                    'at': (datetime.now(dav.SEOUL) - timedelta(days=10)).isoformat(),
                    'used_kib': initial, 'capacity_kib': 1000,
                }]}))
            data = output if output is not None else f'Filesystem 1024-blocks Used Available Capacity Mounted on\n/dev/sda1 1000 {used} {1000-used} 90% /\n'
            with patch.object(dav, 'DISK_HISTORY_PATH', path), \
                 patch.object(dav, 'APP_DIR', Path(directory)), \
                 patch.object(dav, 'run_command', return_value=data):
                text = dav.get_disk_forecast()
            return text, json.loads(path.read_text()) if path.exists() else {}

    def test_growth_predicts_ten_days(self):
        text, history = self.forecast(900, 800)
        self.assertIn('약 10.0일 후 100% 예상', text)
        self.assertIn('평균 증가', text)
        self.assertEqual(len(next(iter(history.values()))), 2)

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
