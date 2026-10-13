"""Offline regressions for pre-upload quota checks and rolling retention."""
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import Mock, patch

import pulsedav as dav


class StorageRetentionTests(unittest.TestCase):
    def setUp(self):
        self.config = dav.WebDAVConfig('https://example.test', '/dav/user', 'user', 'password')
        self.directory = 'tinyGW/site/host'
        self.target = self.directory + '/pulse_20260926_120000.md'
        self.reserve = dav.MIN_REMOTE_FREE_BYTES
        self.print_patch = patch('builtins.print')
        self.print_patch.start()
        self.addCleanup(self.print_patch.stop)

    def entry(self, name, size=100, collection=False):
        return dict(remote_path=self.directory + '/' + name, name=name,
                    size=size, is_collection=collection)

    def prepare(self, entries, quotas, size=100):
        with patch.object(dav, 'list_remote_entries', return_value=entries), \
             patch.object(dav, 'get_remote_available_bytes', side_effect=quotas), \
             patch.object(dav, 'delete_remote_path') as delete:
            result = dav.prepare_remote_space(self.config, self.target, size)
            return result, delete.call_args_list

    def test_exact_reserve_after_upload_needs_no_deletion(self):
        result, calls = self.prepare([], [self.reserve + 100])
        self.assertEqual((result, calls), ([], []))

    def test_at_five_gb_delete_oldest_before_upload(self):
        old = self.entry('pulse_20260101_000000.md')
        newer = self.entry('iptime_20260201_000000.md')
        result, calls = self.prepare([newer, old], [self.reserve, self.reserve + 100])
        self.assertEqual(result, [old['remote_path']])
        self.assertEqual(calls[0].args, (self.config, old['remote_path']))

    def test_below_reserve_replaces_one_report_without_recovering_deficit(self):
        entries = [self.entry('pulse_20260101_000000.md'), self.entry('iptime_20260201_000000.md')]
        available = 1_000_000_000
        result, calls = self.prepare(entries, [available, available + 100])
        self.assertEqual(result, [entries[0]['remote_path']])
        self.assertEqual(len(calls), 1)

    def test_larger_new_report_deletes_only_enough_old_reports(self):
        entries = [self.entry('pulse_20260101_000000.md', 60),
                   self.entry('pulse_20260201_000000.md', 60),
                   self.entry('pulse_20260301_000000.md', 60)]
        available = 1_000_000_000
        result, calls = self.prepare(entries, [available, available + 60, available + 120])
        self.assertEqual(result, [entry['remote_path'] for entry in entries[:2]])
        self.assertEqual(len(calls), 2)

    def test_full_server_replaces_old_report(self):
        entry = self.entry('pulse_20260101_000000.md')
        result, _ = self.prepare([entry], [0, 100])
        self.assertEqual(result, [entry['remote_path']])

    def test_crossing_threshold_triggers_cleanup(self):
        result, _ = self.prepare([self.entry('pulse_20260101_000000.md')],
                                 [self.reserve + 50, self.reserve + 150])
        self.assertEqual(len(result), 1)

    def test_insufficient_candidates_does_not_delete_anything(self):
        with patch.object(dav, 'list_remote_entries', return_value=[self.entry('pulse_20260101_000000.md', 50)]), \
             patch.object(dav, 'get_remote_available_bytes', return_value=self.reserve - 100), \
             patch.object(dav, 'delete_remote_path') as delete:
            with self.assertRaisesRegex(ValueError, '모두 정리해도'):
                dav.prepare_remote_space(self.config, self.target, 100)
            delete.assert_not_called()

    def test_age_retention_deletes_only_this_nodes_sender_markdown(self):
        report = self.entry('pulse_20000101_000000.md')
        iptime = self.entry('iptime_20000101_000000.md')
        entries = [report, iptime, self.entry('notes_20000101_000000.md'),
                   self.entry('pulse_20000101_000000.txt'),
                   self.entry('pulse_20000101_000000.md', collection=True),
                   self.entry('../other/pulse_20000101_000000.md'),
                   self.entry('pulse_20009999_000000.md')]
        with patch.object(dav, 'list_remote_entries', return_value=entries), \
             patch.object(dav, 'delete_remote_path') as delete:
            result = dav.prune_old_remote_files(self.config, self.directory)
        self.assertEqual(result, [report['remote_path'], iptime['remote_path']])
        self.assertEqual(delete.call_count, 2)

    def test_preserves_unrelated_files_folders_other_hosts_and_target(self):
        entries = [self.entry('notes.md', 10000), self.entry('pulse_20250101_000000.md', 10000, True),
                   self.entry('pulse_20260926_120000.md', 10000),
                   self.entry('../other/pulse_20250101_000000.md', 10000)]
        with self.assertRaises(ValueError):
            self.prepare(entries, [self.reserve])

    def test_no_reclaimed_space_stops_further_deletion(self):
        entries = [self.entry('pulse_20260101_000000.md'), self.entry('pulse_20260201_000000.md')]
        with patch.object(dav, 'list_remote_entries', return_value=entries), \
             patch.object(dav, 'get_remote_available_bytes', return_value=self.reserve), \
             patch.object(dav, 'delete_remote_path') as delete:
            with self.assertRaisesRegex(ValueError, '휴지통'):
                dav.prepare_remote_space(self.config, self.target, 100)
            self.assertEqual(delete.call_count, 1)

    def test_put_only_runs_after_space_is_prepared(self):
        events = []
        session = Mock()
        session.put.side_effect = lambda *a, **k: events.append('put') or Mock()
        with patch.object(dav, 'build_session', return_value=session), \
             patch.object(dav, 'ensure_remote_directories'), \
             patch.object(dav, 'prepare_remote_space', side_effect=lambda *a: events.append('prepare') or ['old']):
            self.assertEqual(dav.upload_remote_file(self.config, self.target, b'report'), ['old'])
        self.assertEqual(events, ['prepare', 'put'])
        session.put.reset_mock()
        with patch.object(dav, 'build_session', return_value=session), \
             patch.object(dav, 'ensure_remote_directories'), \
             patch.object(dav, 'prepare_remote_space', side_effect=ValueError('quota')):
            with self.assertRaises(ValueError):
                dav.upload_remote_file(self.config, self.target, b'report')
        session.put.assert_not_called()

    def test_failed_delete_prevents_put(self):
        session = Mock()
        with patch.object(dav, 'build_session', return_value=session), \
             patch.object(dav, 'ensure_remote_directories'), \
             patch.object(dav, 'list_remote_entries', return_value=[self.entry('pulse_20260101_000000.md')]), \
             patch.object(dav, 'get_remote_available_bytes', return_value=self.reserve), \
             patch.object(dav, 'delete_remote_path', side_effect=dav.SimpleRequestException('403')):
            with self.assertRaises(dav.SimpleRequestException):
                dav.upload_remote_file(self.config, self.target, b'report')
        session.put.assert_not_called()

    def serverinfo_response(self, value):
        import json
        return dav.SimpleResponse(200, json.dumps({'ocs': {'meta': {'statuscode': 200},
            'data': {'nextcloud': {'system': {'freespace': value}}}}}), b'')

    def test_serverinfo_zero_and_installation_subpath(self):
        self.config.hostname = 'https://example.test/nextcloud/'
        session = Mock()
        session.request.return_value = self.serverinfo_response(0)
        with patch.object(dav, 'build_session', return_value=session):
            self.assertEqual(dav.get_remote_available_bytes(self.config, self.directory), 0)
        args, kwargs = session.request.call_args
        self.assertEqual(args[0], 'GET')
        self.assertEqual(args[1], 'https://example.test/nextcloud/ocs/v2.php/apps/serverinfo/api/v1/info?format=json&skipApps=true&skipUpdate=true')
        self.assertEqual(kwargs['headers']['OCS-APIRequest'], 'true')
        self.assertEqual(kwargs['timeout'], dav.REQUEST_TIMEOUT)

    def test_serverinfo_positive_value(self):
        session = Mock()
        session.request.return_value = self.serverinfo_response(123456789)
        with patch.object(dav, 'build_session', return_value=session):
            self.assertEqual(dav.get_remote_available_bytes(self.config, self.directory), 123456789)

    def test_invalid_space_prevents_delete_and_upload(self):
        for value in (None, -3, '123', True, 1.5):
            session = Mock()
            session.request.return_value = self.serverinfo_response(value)
            with self.subTest(value=value), patch.object(dav, 'build_session', return_value=session), \
                 patch.object(dav, 'ensure_remote_directories'), \
                 patch.object(dav, 'list_remote_entries', return_value=[self.entry('pulse_20260101_000000.md')]), \
                 patch.object(dav, 'delete_remote_path') as delete:
                with self.assertRaises(dav.WebDAVStorageError):
                    dav.upload_remote_file(self.config, self.target, b'report')
            delete.assert_not_called()
            session.put.assert_not_called()

    def test_serverinfo_rejects_http_and_invalid_ocs_responses(self):
        for status, body in ((401, ''), (403, ''), (404, ''), (200, '<html>login</html>'),
                             (200, '{}'), (200, '{"ocs":{"meta":{"statuscode":997}}}')):
            session = Mock()
            session.request.return_value = dav.SimpleResponse(status, body, b'')
            with self.subTest(status=status, body=body), patch.object(dav, 'build_session', return_value=session):
                with self.assertRaises(dav.WebDAVStorageError):
                    dav.get_remote_available_bytes(self.config, self.directory)

    def test_directory_listing_uses_successful_properties_and_stays_in_scope(self):
        def response(href):
            return f'''<d:response><d:href>{href}</d:href>
            <d:propstat><d:prop><d:quota-available-bytes/></d:prop><d:status>HTTP/1.1 404 Not Found</d:status></d:propstat>
            <d:propstat><d:prop><d:resourcetype/><d:getcontentlength>123</d:getcontentlength></d:prop>
            <d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>'''
        root = ET.fromstring('<d:multistatus xmlns:d="DAV:">' + ''.join(response(p) for p in (
            '/dav/user/' + self.directory + '/pulse_20260101_000000.md',
            '/dav/user/' + self.directory + '/../other/file.md',
            '/dav/username/' + self.directory + '/file.md')) + '</d:multistatus>')
        with patch.object(dav, 'build_session'), patch.object(dav, 'propfind', return_value=root):
            entries = dav.list_remote_entries(self.config, self.directory)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['size'], 123)


if __name__ == '__main__':
    unittest.main()
