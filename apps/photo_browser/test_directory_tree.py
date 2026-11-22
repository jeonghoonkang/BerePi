from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from directory_tree import DirectoryTree
from test_support import create_app


class DirectoryTreeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'originals'
        (self.source / 'nested').mkdir(parents=True)
        Image.new('RGB', (8, 8), 'red').save(self.source / 'first.jpg')
        Image.new('RGB', (8, 8), 'blue').save(self.source / 'nested' / 'second.jpg')
        self.app = create_app(self.root, self.root, self.root / 'db')
        self.library = self.app.extensions['photo_library']
        config = self.library.config()
        config.update(scan_min_free_mb=32, sources=[{'source_id': 'photos', 'protocol': 'file', 'root': str(self.source)}])
        self.library.save_config(config)
        self.library.scan('photos')
        self.library.merge()
        self.managed = Path(self.library.config()['managed_root'])
        self.tree = DirectoryTree(self.library)
        self.client = self.app.test_client()

    def test_roots_and_lazy_one_level_listing(self):
        roots = self.tree.roots()
        self.assertEqual(roots['sources'][0]['source_id'], 'photos')
        directories = self.tree.page('source', 'photos')
        self.assertEqual([item['name'] for item in directories['items']], ['nested'])
        files = self.tree.page('source', 'photos', kind='media')
        self.assertEqual([item['name'] for item in files['items']], ['first.jpg'])
        nested = self.tree.page('source', 'photos', str(self.source / 'nested'), kind='media')
        self.assertEqual([item['name'] for item in nested['items']], ['second.jpg'])
        self.assertEqual(self.tree.page('managed')['items'][0]['name'], 'family')

    def test_directory_and_media_pagination(self):
        for index in range(102):
            (self.source / f'folder{index:03}').mkdir()
            (self.source / f'photo{index:03}.jpg').write_bytes(b'fixture')
        first = self.tree.page('source', 'photos')
        second = self.tree.page('source', 'photos', offset=first['next_offset'])
        self.assertEqual(len(first['items']), 100)
        self.assertEqual(len(second['items']), 3)
        self.assertIsNone(second['next_offset'])
        first_files = self.tree.page('source', 'photos', kind='media')
        self.assertEqual((len(first_files['items']), first_files['total']), (100, 103))

    def test_scope_boundaries_symlinks_hidden_paths_and_unknown_sources(self):
        (self.source / 'outside-link').symlink_to(self.root, target_is_directory=True)
        (self.source / 'inside-link').symlink_to(self.source / 'nested', target_is_directory=True)
        (self.managed / '.trash').mkdir()
        Image.new('RGB', (8, 8)).save(self.managed / '.trash' / 'hidden.jpg')
        names = [item['name'] for item in self.tree.page('source', 'photos')['items']]
        self.assertNotIn('outside-link', names)
        self.assertNotIn('inside-link', names)
        for scope, source_id, path in [
                ('source', 'unknown', str(self.source)), ('source', 'photos', str(self.root)),
                ('managed', None, str(self.source)), ('managed', None, str(self.managed / '.trash')),
                ('source', 'photos', str(self.source / 'inside-link')),
                ('source', 'photos', str(self.source / 'outside-link'))]:
            with self.subTest(scope=scope, path=path), self.assertRaises(ValueError):
                self.tree.checked(scope, source_id, path)

    def test_api_serves_original_and_managed_without_crossing_scope(self):
        original = self.client.get('/api/directory-tree/media', query_string={
            'scope': 'source', 'source_id': 'photos', 'path': str(self.source / 'first.jpg')})
        self.assertEqual(original.status_code, 200)
        original.close()
        managed_file = next(self.managed.rglob('*.jpg'))
        response = self.client.get('/api/directory-tree/media', query_string={
            'scope': 'managed', 'path': str(managed_file), 'download': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response.headers['Content-Disposition'])
        response.close()
        denied = self.client.get('/api/directory-tree/media', query_string={
            'scope': 'source', 'source_id': 'photos', 'path': str(managed_file)})
        self.assertEqual(denied.status_code, 400)
        self.assertEqual(self.client.get('/api/directory-tree', query_string={'scope': 'source',
                          'source_id': 'photos', 'offset': '-1'}).status_code, 400)

    def test_managed_tree_remains_available_when_original_is_offline(self):
        for file in self.source.rglob('*.jpg'): file.unlink()
        (self.source / 'nested').rmdir()
        self.source.rmdir()
        self.assertTrue(self.tree.page('managed')['items'])
        with self.assertRaises(ValueError):
            self.tree.page('source', 'photos')

    def test_new_routes_require_login(self):
        from app import create_app as real_create_app
        with patch.dict(os.environ, {'PHOTO_BROWSER_PASSWORD': 'test-only-password'}):
            client = real_create_app(self.root, self.root, self.library.db).test_client()
            for path in ('/api/directory-tree/roots', '/api/directory-tree?scope=managed',
                         '/api/directory-tree/media?scope=managed', '/api/source-folders'):
                self.assertEqual(client.get(path).status_code, 401)


if __name__ == '__main__':
    unittest.main()
