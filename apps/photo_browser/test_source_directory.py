import base64
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from test_support import create_app


class SourceDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.first, self.second = self.root / 'old-photos', self.root / 'new-photos'
        for folder, color in ((self.first, 'red'), (self.second, 'blue')):
            folder.mkdir()
            Image.new('RGB', (8, 8), color).save(folder / 'photo.jpg')
        self.app = create_app(self.root, self.first, self.root / 'db')
        self.client = self.app.test_client()
        self.library = self.app.extensions['photo_library']
        config = self.library.config()
        config['sources'] = [{'source_id': 'existing', 'protocol': 'file', 'root': str(self.first),
                              'category': 'family', 'owner_id': 'alice', 'recursive': False}]
        self.library.save_config(config)
        self.headers = {'X-Photo-Browser': '1'}

    def register(self, path, headers=None):
        return self.client.post('/api/sources/register-directory', json={'path': str(path)},
                                headers=self.headers if headers is None else headers)

    def test_add_next_source_after_merge_preserves_previous_sources_and_files(self):
        self.library.scan('existing')
        original = self.library.merge()
        copy = Path(original['operations'][0]['destination'])
        contents = copy.read_bytes()
        config = self.library.config()
        response = self.register(self.second)
        self.assertEqual(response.status_code, 201)
        source = response.json['source']
        self.assertTrue(response.json['added'])
        self.assertNotEqual(source['source_id'], 'existing')
        self.assertTrue(source['recursive'])
        stored = self.library.config()
        self.assertEqual(stored['sources'][0], config['sources'][0])
        self.assertEqual(len(stored['sources']), 2)
        self.assertEqual(stored['managed_root'], config['managed_root'])
        self.assertEqual(len(self.library.items()), 1)  # Update registers; scan remains explicit.
        self.library.scan(source['source_id'])
        result = self.library.merge()
        self.assertEqual(sorted(op['status'] for op in result['operations']), ['copied', 'reused'])
        self.assertEqual(copy.read_bytes(), contents)
        self.assertEqual({loc['source_id'] for item in self.library.items()
                          for loc in item['locations'] if loc['role'] == 'source'},
                         {'existing', source['source_id']})
        restarted = create_app(self.root, self.first, self.library.db)
        self.assertEqual(restarted.extensions['photo_library'].config()['sources'], stored['sources'])

    def test_reapplying_existing_directory_reuses_id_and_classification(self):
        previous = self.library.config()
        response = self.register(self.first / '.')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json['added'])
        self.assertEqual(response.json['source'], previous['sources'][0])
        self.assertEqual(self.library.config(), previous)
        first = self.register(self.second).json
        second = self.register(self.second).json
        self.assertEqual(first['source']['source_id'], second['source']['source_id'])
        self.assertFalse(second['added'])

    def test_invalid_or_unauthorized_input_leaves_sources_unchanged(self):
        previous = self.library.config()
        for path in ('', self.root / 'missing', self.root.parent, self.first / 'photo.jpg',
                     self.library.db, previous['managed_root']):
            with self.subTest(path=path):
                self.assertEqual(self.register(path).status_code, 400)
                self.assertEqual(self.library.config(), previous)
        self.assertEqual(self.register(self.second, headers={}).status_code, 403)
        with patch.dict(os.environ, {'PHOTO_BROWSER_PASSWORD': 'secret'}):
            self.assertEqual(self.register(self.second).status_code, 401)
            token = base64.b64encode(b'photo:secret').decode()
            response = self.register(self.second, {**self.headers, 'Authorization': 'Basic ' + token})
            self.assertEqual(response.status_code, 201)

    def test_active_job_blocks_registration_without_replacing_old_source(self):
        entered, release = threading.Event(), threading.Event()
        def scanning(*args, **kwargs):
            entered.set()
            release.wait(5)
            return {'status': 'completed'}
        previous = self.library.config()
        with patch.object(self.library, 'scan', side_effect=scanning):
            try:
                started = self.client.post('/api/scan', json={'source_id': 'existing'}, headers=self.headers)
                self.assertEqual(started.status_code, 202)
                self.assertTrue(entered.wait(2))
                response = self.register(self.second)
                self.assertEqual(response.status_code, 400)
                self.assertIn('실행 중인 작업', response.json['error'])
                self.assertEqual(self.library.config(), previous)
            finally:
                release.set()


if __name__ == '__main__':
    unittest.main()
