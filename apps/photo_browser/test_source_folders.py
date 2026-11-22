import copy
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from PIL import Image

from library import Library
from source_folders import SourceFolders
from test_support import create_app


class SourceFolderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.inbox = self.root / 'inbox'
        self.inbox.mkdir()
        self.library = Library(self.root / 'db', self.root)
        config = self.library.config()
        config['scan_min_free_mb'] = 32
        self.library.save_config(config)
        self.store = SourceFolders(self.library)

    def photo(self, name, color='red'):
        path = self.inbox / name
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (8, 8), color).save(path)
        return path

    def sync(self):
        return self.store.sync(str(self.inbox), lambda _: None, lambda: False)

    def test_named_ids_and_idempotent_incremental_scan_and_copy(self):
        self.photo('가족/first.jpg')
        self.photo('여행/nested/trip.jpg', 'blue')
        registered = self.store.register(str(self.inbox), 'family', 'alice')
        self.assertEqual({r['source']['source_id'] for r in registered['items']}, {'가족', '여행'})
        self.assertEqual(self.sync()['status'], 'completed')
        before = copy.deepcopy(self.library.items())
        managed = {item['media_id']: Path(item['locations'][-1]['path']) for item in before}
        times = {mid: path.stat().st_mtime_ns for mid, path in managed.items()}
        ids = {s['root']: s['source_id'] for s in self.library.config()['sources']}
        self.photo('가족/added.jpg', 'green')
        restarted = SourceFolders(Library(self.library.db, self.root))
        result = restarted.sync(str(self.inbox), lambda _: None, lambda: False)
        self.assertEqual(result['status'], 'completed', result)
        self.assertEqual(len(self.library.items()), 3)
        self.assertEqual({s['root']: s['source_id'] for s in self.library.config()['sources']}, ids)
        for mid, path in managed.items():
            self.assertEqual(path.stat().st_mtime_ns, times[mid])
        self.assertTrue(all(Path(item['locations'][-1]['path']).is_file() for item in self.library.items()))

    def test_invalid_names_collision_existing_source_classification_and_new_folders(self):
        self.photo('Trip photos/a.jpg')
        self.photo('Trip_photos/b.jpg', 'blue')
        self.photo('CON/c.jpg', 'green')
        first = self.store.register(str(self.inbox))
        ids = [item['source']['source_id'] for item in first['items']]
        self.assertEqual(len(set(ids)), 3)
        self.assertIn('Trip_photos', ids)
        self.assertIn('folder_CON', ids)
        before = copy.deepcopy(self.library.config()['sources'])
        self.store.register(str(self.inbox), 'changed', 'other')
        self.assertEqual(self.library.config()['sources'], before)
        self.photo('new/new.jpg', 'yellow')
        result = self.sync()
        self.assertEqual(result['status'], 'completed', result)
        new = next(s for s in self.library.config()['sources'] if s['source_id'] == 'new')
        self.assertEqual((new['category'], new['owner_id']), ('changed', 'other'))

    def test_existing_ids_reused_and_other_sources_never_scanned_or_merged(self):
        path = self.photo('photos/a.jpg')
        outside = self.root / 'unrelated'
        outside.mkdir()
        Image.new('RGB', (8, 8), 'blue').save(outside / 'b.jpg')
        config = self.library.config()
        config['sources'] = [{'source_id': 'legacy', 'protocol': 'file', 'root': str(path.parent),
                              'category': 'legacy_cat', 'owner_id': 'bob'},
                             {'source_id': 'other', 'protocol': 'file', 'root': str(outside)}]
        self.library.save_config(config)
        self.library.scan('other')
        self.store.register(str(self.inbox))
        result = self.sync()
        self.assertEqual(result['status'], 'completed', result)
        self.assertEqual([entry['source_id'] for entry in result['items']], ['legacy'])
        other = next(item for item in self.library.items() if item['locations'][0]['source_id'] == 'other')
        self.assertFalse(any(loc['role'] == 'managed' for loc in other['locations']))

    def test_empty_deleted_and_new_child_directories_do_not_delete_old_sources(self):
        self.photo('photos/a.jpg')
        (self.inbox / 'empty').mkdir()
        self.store.register(str(self.inbox))
        self.assertEqual(self.sync()['status'], 'completed')
        (self.inbox / 'photos' / 'a.jpg').unlink()
        (self.inbox / 'photos').rmdir()
        result = self.sync()
        self.assertEqual(result['status'], 'completed', result)
        self.assertIn('photos', {s['source_id'] for s in self.library.config()['sources']})
        self.assertTrue(any(loc['role'] == 'managed' for item in self.library.items() for loc in item['locations']))

    def test_excluded_paths_and_invalid_input_are_safe(self):
        self.photo('photos/a.jpg')
        (self.inbox / '.hidden').mkdir()
        (self.inbox / 'linked').symlink_to(self.root, target_is_directory=True)
        config = self.library.config()
        config['managed_root'] = str(self.inbox / 'managed')
        self.library.save_config(config)
        (self.inbox / 'managed').mkdir(exist_ok=True)
        result = self.store.register(str(self.inbox))
        self.assertEqual([r['source']['source_id'] for r in result['items']], ['photos'])
        self.assertEqual(len(result['skipped']), 3)
        before = self.library.config()
        for invalid in ('', str(self.root.parent), str(self.library.db), str(self.inbox / 'managed')):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.store.register(invalid)
        self.assertEqual(self.library.config(), before)

    def test_stop_and_failed_scan_never_start_merge(self):
        self.photo('photos/a.jpg')
        self.store.register(str(self.inbox))
        with patch.object(self.library, 'merge', side_effect=AssertionError('Must not merge')):
            self.assertEqual(self.store.sync(str(self.inbox), lambda _: None, lambda: True)['status'], 'stopped')
            with patch.object(self.library, 'scan', return_value={'status': 'failed', 'published': False}):
                result = self.sync()
                self.assertEqual((result['status'], result['error_count']), ('failed', 1))

    def test_api_batch_stop_exclusivity_and_persisted_settings(self):
        self.photo('photos/a.jpg')
        app = create_app(self.root, self.root, self.library.db)
        client = app.test_client()
        headers = {'X-Photo-Browser': '1'}
        self.assertEqual(client.post('/api/source-folders', json={'root': str(self.inbox)}).status_code, 403)
        self.assertEqual(client.post('/api/source-folders', json={'root': str(self.inbox)}, headers=headers).status_code, 200)
        self.assertEqual(client.get('/api/source-folders').json['items'][0]['sources'][0]['source_id'], 'photos')
        entered, release = threading.Event(), threading.Event()
        def scan(*args, **kwargs):
            entered.set(); release.wait(5)
            return {'status': 'stopped', 'published': False}
        with patch.object(app.extensions['photo_library'], 'scan', side_effect=scan):
            try:
                response = client.post('/api/source-folders/sync', json={'root': str(self.inbox)}, headers=headers)
                self.assertEqual(response.status_code, 202)
                self.assertTrue(entered.wait(2))
                blocked = client.post('/api/scan', json={'source_id': 'photos'}, headers=headers)
                self.assertEqual(blocked.status_code, 400)
                config_change = client.put('/api/config', json=self.library.config(), headers=headers)
                self.assertEqual(config_change.status_code, 400)
                job_id = response.json['job_id']
                self.assertEqual(client.post('/api/jobs/' + job_id + '/stop', json={}, headers=headers).status_code, 200)
            finally:
                release.set()
            for _ in range(200):
                status = client.get('/api/jobs/' + job_id).json
                if status['status'] == 'stopped': break
                time.sleep(.01)
            self.assertEqual(status['status'], 'stopped')


if __name__ == '__main__':
    unittest.main()
