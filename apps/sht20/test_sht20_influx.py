"""Control-flow tests without a live database, sensor or Telegram account."""
import datetime
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

ZoneInfo('Asia/Seoul')  # Initialize timezone data before isolating optional imports.


spec = importlib.util.spec_from_file_location('sht20_report_under_test', Path(__file__).with_name('sht20_influx.py'))
report = importlib.util.module_from_spec(spec)
with patch.dict('sys.modules', {name: MagicMock() for name in (
        'pandas', 'matplotlib', 'matplotlib.pyplot', 'seaborn', 'influxdb',
        'rich', 'rich.console')}):
    spec.loader.exec_module(report)


class ReportTests(unittest.TestCase):
    def test_empty_query_never_uses_existing_image(self):
        client = MagicMock()
        client.query.return_value.get_points.return_value = []
        start = datetime.datetime(2026, 11, 1, tzinfo=datetime.timezone(datetime.timedelta(hours=9)))
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / 'week_1.png'
            image.write_bytes(b'old image')
            self.assertFalse(report.render_week(client, 'temperature', 'value', start,
                                                start + datetime.timedelta(days=7), image))
            self.assertEqual(image.read_bytes(), b'old image')
        query = client.query.call_args.args[0]
        self.assertIn('2026-10-31T15:00:00Z', query)

    def test_latest_time_and_empty_database(self):
        self.assertIn('2026-09-27 15:05:35 KST', report.latest_data_text([
            {'time': '2026-09-27T06:05:35.344512Z', 'value': 38.9}]))
        self.assertIn('없음', report.latest_data_text([]))

    def test_main_sends_notices_only_for_empty_ranges(self):
        with patch.object(report, 'InfluxDBClient') as factory, \
             patch.object(report, 'fetch_recent_values', return_value=[]), \
             patch.object(report, 'render_week', side_effect=[False, True, False, False]), \
             patch.object(report, 'send_image') as image, \
             patch.object(report, 'send_no_data') as notice:
            report.main()
            self.assertEqual(image.call_count, 1)
            self.assertEqual(notice.call_count, 3)
            self.assertIn('없음', notice.call_args.args[2])
            factory.return_value.close.assert_called_once()

    def test_field_setting_and_message_content(self):
        client = MagicMock()
        with patch.object(report, 'INFLUX_FIELD', 'temperature_c'):
            report.fetch_recent_values(client)
        self.assertIn('SELECT "temperature_c"', client.query.call_args.args[0])
        start = datetime.datetime(2026, 11, 1)
        with patch.object(report.subprocess, 'run') as run:
            report.send_no_data(start, start, '가장 최근 데이터: 없음')
        command = run.call_args.args[0]
        self.assertEqual(command[:2], ['telegram-send', '--'])
        self.assertIn('조회 기간 (KST)', command[2])
        self.assertIn('가장 최근 데이터: 없음', command[2])


if __name__ == '__main__':
    unittest.main()
