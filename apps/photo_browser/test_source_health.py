import copy
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from PIL import Image
from library import Library
from source_health import SourceHealth, audit_lock
from test_support import create_app


class SourceHealthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'photos'; self.source.mkdir()
        self.file = self.source / 'photo.jpg'
        Image.new('RGB', (8, 8), 'red').save(self.file)
        self.library = Library(self.root / 'db', self.root)
        config = self.library.config()
        config.update(scan_min_free_mb=32, sources=[{'source_id': 'photos', 'protocol': 'file', 'root': str(self.source)}])
        self.library.save_config(config)
        self.library.scan('photos'); self.library.merge()
        self.before = copy.deepcopy(self.library.items()[0])
        self.output = io.StringIO()
        self.health = SourceHealth(self.library, self.output)

    def check(self, second=0):
        return self.health.check(at='2026-11-22T00:{:02d}:{:02d}+00:00'.format(second // 60, second % 60))

    def events(self):
        result = []
        for path in (self.health.directory / 'events').glob('*.jsonl'):
            result.extend(json.loads(line) for line in path.read_text().splitlines())
        return result

    def test_original_lookup_does_not_change_catalog(self):
        result = self.health.origins(self.before['media_id'])
        self.assertEqual(result['items'][0]['path'], str(self.file))
        self.assertEqual(result['items'][0]['health'], 'ok')
        with patch('source_health.digest', side_effect=AssertionError('Healthy file must not be hashed')):
            self.assertEqual(self.check()['active_count'], 0)
        self.assertEqual(self.library.item(self.before['media_id']), self.before)

    def test_missing_repeat_restart_and_resolution_are_durable(self):
        self.file.rename(self.source / 'moved.jpg')
        self.assertEqual(self.check()['active_count'], 1)
        issue_id = self.health.page()['items'][0]['issue_id']
        self.check(30)
        self.assertEqual(len(self.events()), 1)
        self.health = SourceHealth(Library(self.library.db, self.root), self.output)
        self.check(60)
        self.assertEqual(self.health.page()['items'][0]['issue_id'], issue_id)
        self.assertEqual([event['event'] for event in self.events()], ['detected', 'unresolved'])
        self.assertEqual(self.events()[-1]['elapsed_seconds'], 60)
        (self.source / 'moved.jpg').rename(self.file)
        self.assertEqual(self.check(90)['active_count'], 0)
        resolved = self.health.page('resolved')['items'][0]
        self.assertEqual((resolved['status'], resolved['resolution']), ('resolved', 'original_access_restored'))
        self.assertIn('KST', self.output.getvalue())
        self.assertEqual(self.library.item(self.before['media_id']), self.before)

    def test_find_and_verified_repair_preserve_identity_tags_dates_and_managed_file(self):
        moved = self.source / 'nested' / 'renamed.jpg'; moved.parent.mkdir()
        self.file.rename(moved)
        self.check()
        issue = self.health.page()['items'][0]
        self.assertEqual(self.health.find(issue['issue_id'])['candidates'], [str(moved)])
        self.health.repair(issue['issue_id'], str(moved))
        item = self.library.item(self.before['media_id'])
        self.assertEqual(item['locations'][0]['path'], str(moved))
        for key in ('media_id', 'classification', 'capture'):
            self.assertEqual(item[key], self.before[key])
        self.assertEqual(item['locations'][1:], self.before['locations'][1:])
        self.assertEqual(self.health.page('resolved')['items'][0]['resolution'], 'verified_db_path_updated')
        self.library.scan('photos')
        self.assertEqual(len(self.library.items()), 1)

    def test_wrong_content_outside_root_and_managed_copy_cannot_repair_source(self):
        self.file.rename(self.source / 'moved.jpg'); self.check()
        issue = self.health.page()['items'][0]
        bad = self.source / 'wrong.jpg'; Image.new('RGB', (8, 8), 'blue').save(bad)
        outside = self.root / 'outside.jpg'; outside.write_bytes((self.source / 'moved.jpg').read_bytes())
        for path in (bad, outside, Path(self.before['locations'][-1]['path'])):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.health.repair(issue['issue_id'], str(path))
        self.assertEqual(self.library.item(self.before['media_id']), self.before)
        self.assertEqual(self.health.summary()['active_count'], 1)

    def test_root_disconnect_does_not_resolve_preexisting_file_problem(self):
        self.file.rename(self.source / 'moved.jpg'); self.check()
        offline = self.root / 'offline'; self.source.rename(offline)
        self.check(60)
        self.assertEqual(self.health.summary()['active_count'], 2)
        self.assertEqual(self.health.page('resolved')['total'], 0)
        offline.rename(self.source); self.check(90)
        self.assertEqual(self.health.summary()['active_count'], 1)

    def test_removed_db_reference_is_closed_not_claimed_file_restored(self):
        self.file.unlink(); self.check()
        item = self.library.items()[0]; item['lifecycle']['status'] = 'trashed'
        with self.library.writing(): self.library.commit([item])
        self.check(60)
        record = self.health.page('resolved')['items'][0]
        self.assertEqual(record['status'], 'closed')
        self.assertEqual(record['resolution'], 'db_reference_removed_or_changed')

    def test_content_change_and_permission_errors_are_not_reported_as_move(self):
        self.file.write_bytes(b'changed')
        self.check()
        self.assertEqual(self.health.page()['items'][0]['kind'], 'content_changed')
        with patch.object(self.health, 'confined', side_effect=PermissionError('denied')):
            self.check(60)
        self.assertEqual(self.health.page()['items'][0]['kind'], 'access_denied')

    def test_monitor_can_record_during_scan_but_pauses_for_backup_audit_lock(self):
        self.file.unlink()
        entered, release = threading.Event(), threading.Event()
        def writer():
            with self.library.writing():
                entered.set(); release.wait(3)
        thread = threading.Thread(target=writer); thread.start()
        try:
            self.assertTrue(entered.wait(1))
            self.assertEqual(self.check()['active_count'], 1)
        finally:
            release.set(); thread.join(3)
        with audit_lock(self.library.db):
            self.assertEqual(self.check(30)['status'], 'busy')
        self.assertEqual(len(self.events()), 1)

    def test_catalog_change_during_check_never_publishes_stale_resolution(self):
        self.file.unlink()
        with patch.object(self.health, 'catalog_signature', side_effect=['one', 'two']):
            self.assertEqual(self.check()['status'], 'retry')
        self.assertIsNone(self.health.summary()['checked_at'])

    def test_monitor_lifecycle_runs_without_browser_and_stops(self):
        self.file.unlink()
        with self.health.running(interval=.02):
            deadline = time.monotonic() + 2
            while self.health.summary().get('active_count') != 1 and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertEqual(self.health.summary()['active_count'], 1)
        self.assertFalse(any(thread.name == 'photo-source-health' for thread in threading.enumerate()))

    def test_resolved_audit_survives_backup_and_relocation(self):
        from backup import create_backup, restore_backup
        self.file.rename(self.source / 'moved.jpg'); self.check()
        (self.source / 'moved.jpg').rename(self.file); self.check(60)
        bundle = self.root / 'backup.zip'; create_backup(self.library, bundle)
        restored = restore_backup(bundle, self.root / 'restore')
        health = SourceHealth(Library(restored['db'], restored['root']))
        self.assertEqual(health.page('resolved')['total'], 1)

    def test_api_and_cli_lookup_status_find_repair_and_auth(self):
        app = create_app(self.root, self.root, self.library.db)
        client = app.test_client(); headers = {'X-Photo-Browser': '1'}
        self.assertEqual(client.get('/api/library/' + self.before['media_id'] + '/sources').json['items'][0]['health'], 'ok')
        self.file.rename(self.source / 'moved.jpg'); self.check()
        issue = self.health.page()['items'][0]
        self.assertEqual(client.get('/api/source-path-health').json['active_count'], 1)
        self.assertEqual(client.post('/api/source-path-health/check').status_code, 403)
        response = client.post('/api/source-path-health/repair', json={'issue_id': issue['issue_id'],
            'path': str(self.source / 'moved.jpg')}, headers=headers)
        self.assertEqual(response.status_code, 202)
        for _ in range(200):
            job = client.get('/api/jobs/' + response.json['job_id']).json
            if job['status'] not in {'queued', 'running'}: break
            time.sleep(.01)
        self.assertEqual(job['status'], 'completed', job)
        from cli import main
        from contextlib import redirect_stdout, redirect_stderr
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(io.StringIO()):
            self.assertEqual(main(['--db', str(self.library.db), '--root', str(self.root),
                                   'original-paths', '--media-id', self.before['media_id']]), 0)
        self.assertEqual(json.loads(output.getvalue())['items'][0]['path'], str(self.source / 'moved.jpg'))
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(io.StringIO()):
            self.assertEqual(main(['--db', str(self.library.db), '--root', str(self.root), 'source-health', '--resolved']), 0)
        self.assertEqual(json.loads(output.getvalue())['items'][0]['resolution'], 'verified_db_path_updated')

    def test_new_health_apis_do_not_expose_paths_without_login(self):
        from app import create_app as real_create_app
        with patch.dict(os.environ, {'PHOTO_BROWSER_PASSWORD': 'test-only-password'}):
            client = real_create_app(self.root, self.root, self.library.db).test_client()
            for url in ('/api/source-path-health', '/api/source-path-health/issues',
                        '/api/library/' + self.before['media_id'] + '/sources'):
                response = client.get(url)
                self.assertEqual(response.status_code, 401)
                self.assertNotIn(str(self.source), response.get_data(as_text=True))


if __name__ == '__main__': unittest.main()
