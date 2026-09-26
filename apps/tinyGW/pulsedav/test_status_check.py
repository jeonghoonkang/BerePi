import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from xml.sax.saxutils import escape

import status_check as sc
from pulsedav import WebDAVConfig


def xml_response(path, directory=False, modified='Sat, 26 Sep 2026 02:00:00 GMT'):
    kind = '<d:collection/>' if directory else ''
    return f'<d:response><d:href>{escape(path)}</d:href><d:propstat><d:prop><d:resourcetype>{kind}</d:resourcetype><d:getlastmodified>{modified}</d:getlastmodified></d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>'


class Response:
    def __init__(self, text):
        self.text = text
    def raise_for_status(self):
        pass


class Session:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []
    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        value = self.pages[url]
        if isinstance(value, Exception):
            raise value
        return Response(value)


class StatusTests(unittest.TestCase):
    def test_cron_quoted_config_and_comments(self):
        paths, bad = sc.cron_configs('''# */30 * * * * cd /tmp/pulsedav && python3 sender.py --config ignored.json
*/30 * * * * cd '/tmp/pulsedav space' && python3 sender.py --once --config 'my settings.json'
@reboot python3 /tmp/pulsedav/sender.py --config=/tmp/config.json
''', '/home/test')
        self.assertEqual(paths, {Path('/tmp/pulsedav space/my settings.json').resolve(), Path('/tmp/config.json').resolve()})
        self.assertFalse(bad)

    def test_watchdog_cron_is_not_a_report_config(self):
        paths, bad = sc.cron_configs('0 * * * * cd /tmp/pulsedav && python3 sender.py --gateway-watchdog', '/tmp')
        self.assertEqual(paths, set())
        self.assertFalse(bad)

    def test_check_status_rejects_other_modes(self):
        import sender
        for mode in ('--gateway-watchdog', '--install-crontab', '--once'):
            with self.subTest(mode=mode), patch('sys.argv', ['sender.py', '--check-status', mode]), patch('sys.stderr'):
                with self.assertRaises(SystemExit) as error:
                    sender.parse_args()
                self.assertEqual(error.exception.code, 2)

    def test_status_scopes_and_multiple_upload_directories(self):
        local = ['tinyGW/site-a/local', 'tinyGW/site-b/local']
        other = 'tinyGW/site-a/other'
        stamp = datetime.now(timezone.utc).isoformat()
        def fake_scan(session, config, target):
            hosts = local + [other] if target == 'tinyGW' else [target]
            return hosts, [{'path': h + '/pulse_now.md', 'modified_at': stamp} for h in hosts], []
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / 'config.json'
            config.write_text(json.dumps({'webdav': {'hostname': 'https://example.test', 'username': 'u', 'password': 'test'}}))
            inventory = Path(tmp) / 'inventory.json'
            inventory.write_text(json.dumps([{'directory': other, 'server_name': 'other'}]))
            for all_nodes in (False, True):
                with self.subTest(all_nodes=all_nodes), patch.object(sc, 'discover_config', return_value=(config, [])), patch.object(sc, 'build_session'), patch.object(sc, 'build_host_remote_dirs', return_value=local), patch.object(sc, 'scan', side_effect=fake_scan) as scan, patch.object(sc, 'report_metadata', return_value={}), patch('builtins.print'):
                    self.assertEqual(sc.check_status(str(config), tmp, server_list=str(inventory), all_nodes=all_nodes), 0)
                result = json.loads((Path(tmp) / 'server_status.json').read_text())
                self.assertEqual([call.args[2] for call in scan.call_args_list], ['tinyGW'] if all_nodes else local)
                self.assertEqual({row['directory'] for row in result['servers']}, set(local + [other] if all_nodes else local))
                self.assertEqual(result['scope'], 'all' if all_nodes else 'local')
                tree = (Path(tmp) / 'server_status.txt').read_text()
                self.assertIn('site-a/', tree)
                self.assertIn('site-b/', tree)
                self.assertEqual('other/' in tree, all_nodes)

    def test_all_status_conflicts_and_cron_exclusion(self):
        import sender
        for flag in ('--check-status', '--once', '--install-crontab', '--gateway-watchdog'):
            with self.subTest(flag=flag), patch('sys.argv', ['sender.py', '--check-status-all', flag]), patch('sys.stderr'):
                with self.assertRaises(SystemExit) as error:
                    sender.parse_args()
                self.assertEqual(error.exception.code, 2)
        self.assertEqual(sc.cron_configs('0 * * * * cd /tmp/pulsedav && python3 sender.py --check-status-all', '/tmp'), (set(), False))

    def test_unresolved_shell_variable(self):
        self.assertTrue(sc.cron_configs('*/30 * * * * python3 /tmp/pulsedav/sender.py --config "$CONFIG"', '/tmp')[1])

    def test_recursive_scan_and_partial_failure(self):
        config = WebDAVConfig('https://example.test', '/remote.php/dav/files/u', 'u', 'secret')
        base = '/remote.php/dav/files/u/'
        def page(*items):
            return '<d:multistatus xmlns:d="DAV:">' + ''.join(items) + '</d:multistatus>'
        session = Session({
            'https://example.test' + base + 'tinyGW': page(xml_response(base+'tinyGW/', True), xml_response(base+'tinyGW/sub/', True), xml_response(base+'tinyGW/broken/', True)),
            'https://example.test' + base + 'tinyGW/sub': page(xml_response(base+'tinyGW/sub/', True), xml_response(base+'tinyGW/sub/host/', True)),
            'https://example.test' + base + 'tinyGW/sub/host': page(xml_response(base+'tinyGW/sub/host/', True), xml_response(base+'tinyGW/sub/host/a%20%23%3F.md')),
            'https://example.test' + base + 'tinyGW/broken': OSError('connection refused'),
        })
        directories, files, errors = sc.scan(session, config, 'tinyGW')
        self.assertIn('tinyGW/sub/host', directories)
        self.assertEqual(files[0]['path'], 'tinyGW/sub/host/a #?.md')
        self.assertEqual(files[0]['modified_at'], '2026-09-26T11:00:00+09:00')
        self.assertEqual(errors[0]['error'], 'connection_refused')
        self.assertTrue(all(c[0] == 'PROPFIND' and c[2]['headers']['Depth'] == '1' for c in session.calls))

    def test_latest_and_timezones(self):
        self.assertEqual(sc.iso_time('2026-09-26T11:00:00+09:00'), '2026-09-26T11:00:00+09:00')
        self.assertEqual(sc.iso_time('2026-09-25T23:30:00Z'), '2026-09-26T08:30:00+09:00')
        self.assertIsNone(sc.iso_time('invalid'))
        self.assertEqual(sc.latest([{'modified_at': None}, {'modified_at': '2026-01-01T00:00:00+00:00'}])['modified_at'], '2026-01-01T00:00:00+00:00')

    def test_recording_health_not_masked_by_new_other_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'settings.json'
            path.write_text(json.dumps({'webdav': {'hostname': 'https://example.test', 'root': '/dav', 'username': 'u', 'password': 'secret'}}))
            files = [{'path': 'tinyGW/host/pulse_old.md', 'modified_at': '2020-01-01T00:00:00+00:00'}, {'path': 'tinyGW/host/other.txt', 'modified_at': datetime.now(timezone.utc).isoformat()}]
            with patch.object(sc, 'discover_config', return_value=(path, ['test'])), patch.object(sc, 'build_session'), patch.object(sc, 'build_host_remote_dirs', return_value=['tinyGW/host']), patch.object(sc, 'scan', return_value=(['tinyGW','tinyGW/host'], files, [])), patch.object(sc, 'report_metadata', return_value={'server_name': 'host', 'ip_address': '10.0.0.2', 'open_port': '22'}), patch('builtins.print'):
                code = sc.check_status(str(path), tmp)
            result = json.loads((Path(tmp)/'server_status.json').read_text())
            self.assertEqual(code, 1)
            self.assertEqual(result['servers'][0]['status'], 'stale')
            self.assertEqual(result['servers'][0]['latest_file'], 'tinyGW/host/other.txt')
            self.assertNotIn('secret', (Path(tmp)/'server_status.json').read_text())
            self.assertIn('pulse_old.md', (Path(tmp)/'server_status.txt').read_text())

    def test_all_tree_summarizes_markdown_per_directory_only(self):
        files = [
            {'path': 'tinyGW/host/z_old.md', 'modified_at': '2026-09-25T11:00:00+09:00'},
            {'path': 'tinyGW/host/a_new.MD', 'modified_at': '2026-09-26T11:00:00+09:00'},
            {'path': 'tinyGW/host/info.txt', 'modified_at': None},
            {'path': 'tinyGW/host/sub/child.md', 'modified_at': '2026-09-26T12:00:00+09:00'},
        ]
        result = {'target_directory': 'tinyGW', 'scan_complete': True, 'checked_at': 'now', 'scope': 'all', 'cron_notes': [], 'directories': ['tinyGW', 'tinyGW/host', 'tinyGW/host/sub'], 'servers': [], 'files': files, 'errors': []}
        tree = sc.render_tree(result)
        self.assertNotIn('z_old.md', tree)
        self.assertIn('a_new.MD  2026-09-26T11:00:00+09:00 [MD 총 2개, 최신 1개 표시]', tree)
        self.assertIn('child.md', tree)
        self.assertIn('info.txt', tree)
        self.assertEqual(len(result['files']), 4)
        result['scope'] = 'local'
        self.assertIn('z_old.md', sc.render_tree(result))
        self.assertNotIn('MD 총', sc.render_tree(result))

    def test_markdown_summary_does_not_claim_unknown_time_is_latest(self):
        result = {'target_directory': 'tinyGW', 'scan_complete': False, 'checked_at': 'now', 'scope': 'all', 'cron_notes': [], 'directories': ['tinyGW'], 'servers': [], 'files': [{'path': 'tinyGW/a.md', 'modified_at': None}, {'path': 'tinyGW/b.md', 'modified_at': None}], 'errors': []}
        tree = sc.render_tree(result)
        self.assertIn('수정 시각 미확인 2개, 대표 1개 표시', tree)
        self.assertNotIn('최신', tree)
        self.assertNotIn('b.md', tree)

    def test_tree_siblings_and_nested_folders(self):
        tree = sc.render_tree({'target_directory':'tinyGW','scan_complete':True,'checked_at':'now','cron_notes':[], 'directories':['tinyGW','tinyGW/a','tinyGW/a/b','tinyGW/z'], 'servers':[], 'files':[{'path':'tinyGW/a/b/f','modified_at':None},{'path':'tinyGW/z/g','modified_at':None}], 'errors':[]})
        self.assertIn('│       └── f', tree)
        self.assertIn('└── z/\n    └── g', tree)


if __name__ == '__main__':
    unittest.main()
