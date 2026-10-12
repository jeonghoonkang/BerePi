import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import check_tinyGW_all as check


def report(stamp, rows):
    return f'- 호스트명: host\n- 내부 IP: 192.168.1.2\n- 생성 시각: {stamp} KST\n## HDD 공간\n```text\n{rows}\n```\n'


class AggregateTests(unittest.TestCase):
    def test_remote_downloads_latest_named_report_only(self):
        session = Mock()
        session.request.return_value.content = report('2026-10-13 10:00:00', 'no disk data').encode()
        entries = [{'path': f'tinyGW/host/pulse_202610{day}_100000.md', 'is_directory': False}
                   for day in ('12', '13')]
        with patch.object(check, 'build_session', return_value=session), \
             patch.object(check, 'list_directory', return_value=entries):
            reports, _ = check.collect_webdav({'webdav': {'hostname': 'https://example.test'}})
        self.assertEqual(len(reports), 1)
        session.request.assert_called_once()
        self.assertIn('20261013', session.request.call_args.args[1])

    def test_dns_category_survives_scan_wrapper(self):
        from pulsedav import REQUEST_ERRORS
        session = Mock()
        error = REQUEST_ERRORS[0]('nodename nor servname provided, or not known')
        with patch.object(check, 'build_session', return_value=session), \
             patch.object(check, 'list_directory', side_effect=error), \
             patch('sys.argv', ['check']), patch('builtins.print') as output:
            self.assertEqual(check.main(), 1)
        text = '\n'.join(str(call.args[0]) for call in output.call_args_list)
        self.assertIn('dns_error', text)
        self.assertIn('DNS', text)

    def test_missing_config_does_not_connect(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch('sys.argv', ['check', '--config', str(Path(directory) / 'missing.json')]), \
             patch.object(check, 'collect_webdav') as collect, patch('builtins.print'):
            self.assertEqual(check.main(), 1)
        collect.assert_not_called()

    def test_http_error_is_actionable_without_response_body(self):
        from pulsedav import SimpleRequestException
        with patch('sys.argv', ['check']), \
             patch.object(check, 'collect_webdav', side_effect=RuntimeError('PROPFIND: HTTP 401: secret')), \
             patch('builtins.print') as output:
            self.assertEqual(check.main(), 1)
        text = '\n'.join(str(call.args[0]) for call in output.call_args_list)
        self.assertIn('HTTP 401', text)
        self.assertNotIn('secret', text)

    def test_remote_scan_and_save_before_send(self):
        data = report('2026-10-13 10:00:00', 'Filesystem Size(GiB) Used Available Use% Mounted on\n/dev/data 200 180 20 90% /')
        session = Mock()
        session.request.return_value.content = data.encode('utf-8')
        entries = [[{'path': 'tinyGW/host', 'is_directory': True}],
                   [{'path': 'tinyGW/host/pulse_20261013_100000.md', 'is_directory': False}]]
        with patch.object(check, 'build_session', return_value=session), \
             patch.object(check, 'list_directory', side_effect=entries):
            reports, errors = check.collect_webdav({'webdav': {'hostname': 'https://example.test'}})
        self.assertFalse(errors)
        self.assertEqual(len(reports), 1)
        self.assertIn('/tinyGW/host/', session.request.call_args.args[1])
        session.close.assert_called_once()
        with tempfile.TemporaryDirectory() as directory:
            def send(message, *args):
                files = list(Path(directory).glob('*.txt'))
                self.assertEqual(len(files), 1)
                self.assertEqual(message, files[0].read_text())
            with patch('sys.argv', ['check', '--send', '--logs-dir', directory]), \
                 patch.object(check, 'collect_webdav', return_value=(reports, [])), \
                 patch.object(check, 'send_text', side_effect=send) as sender, \
                 patch('builtins.print'):
                self.assertEqual(check.main(), 0)
            sender.assert_called_once()

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
        progress = Mock()
        with patch.object(check.subprocess, 'run', return_value=Mock(returncode=0)) as run:
            check.send_text('x' * 4000, 'telegram-send', '/tmp/bot.conf', 12, progress)
        self.assertEqual(run.call_count, 3)
        self.assertEqual(''.join(c.args[0][-1] for c in run.call_args_list), 'x' * 4000)
        self.assertNotIn('--file', run.call_args.args[0])
        self.assertEqual(progress.call_count, 6)
        self.assertIn('전송 시작 #1', progress.call_args_list[0].args[0])
        self.assertIn('전송 완료 #3', progress.call_args_list[-1].args[0])
