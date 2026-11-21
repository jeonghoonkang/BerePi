import tempfile
import copy
import threading
import unittest
from pathlib import Path

from PIL import Image

from test_support import create_app
from scan_duplicates import ScanDuplicateIndex, duplicate_page


class ScanDuplicateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.a, self.b = self.root / 'a', self.root / 'b'
        self.a.mkdir(); self.b.mkdir()
        Image.new('RGB', (8, 8), 'red').save(self.a / 'original.jpg')
        self.app = create_app(self.root, self.root, self.root / 'db')
        self.library = self.app.extensions['photo_library']
        self.library.save_config({'managed_root': str(self.root / 'managed'), 'scan_min_free_mb': 32,
                                  'sources': [{'source_id': 'a', 'protocol': 'file', 'root': str(self.a), 'category': 'family', 'owner_id': 'alice'},
                                              {'source_id': 'b', 'protocol': 'file', 'root': str(self.b), 'category': 'travel', 'owner_id': 'bob'}]})
        self.library.scan('a')

    def tearDown(self):
        self.temp.cleanup()

    def test_renamed_copy_reports_existing_classification_and_managed_path(self):
        self.library.merge()
        (self.b / 'renamed.jpg').write_bytes((self.a / 'original.jpg').read_bytes())
        result = self.library.scan('b')
        self.assertEqual(result['cross_group_duplicate_count'], 1)
        page = duplicate_page(self.library, result['scan_id'])
        self.assertEqual(page['total'], 1)
        match = page['items'][0]['matches'][0]
        self.assertEqual((match['category_id'], match['owner_id'], match['source_ids']), ('family', 'alice', ['a']))
        self.assertTrue(match['managed_files'][0]['exists'])
        self.assertTrue(Path(match['managed_files'][0]['path']).is_file())
        response = self.app.test_client().get(f'/api/scans/{result["scan_id"]}/duplicates')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['total'], 1)
        page = self.app.test_client().get('/').get_data(as_text=True)
        self.assertLess(page.index('scan_duplicates.js'), page.index('library.js'))

    def test_same_name_different_bytes_and_self_do_not_match(self):
        Image.new('RGB', (8, 8), 'blue').save(self.b / 'original.jpg')
        self.assertEqual(self.library.scan('b')['cross_group_duplicate_count'], 0)
        self.assertEqual(self.library.scan('a')['cross_group_duplicate_count'], 0)

    def test_category_or_owner_difference_matches_with_the_same_source_id(self):
        original = self.library.items()[0]
        for key, value in [('category_id', 'travel'), ('owner_id', 'bob')]:
            with self.subTest(key=key):
                existing = copy.deepcopy(original)
                existing['media_id'] = 'other-id'
                existing['classification'][key] = value
                result = ScanDuplicateIndex(self.library, [existing]).check(original)
                self.assertEqual(result['match_count'], 1)
                self.assertEqual(result['matches'][0][key], value)

    def test_other_source_same_category_owner_is_also_reported(self):
        config = self.library.config()
        config['sources'][1].update(category='family', owner_id='alice')
        self.library.save_config(config)
        (self.b / 'photo.jpg').write_bytes((self.a / 'original.jpg').read_bytes())
        result = self.library.scan('b')
        self.assertEqual(result['cross_group_duplicate_count'], 1)
        match = duplicate_page(self.library, result['scan_id'])['items'][0]['matches'][0]
        self.assertEqual(match['managed_files'], [])

    def test_inactive_records_are_excluded(self):
        items = self.library.items()
        items[0]['lifecycle']['status'] = 'trashed'
        self.library.commit(items)
        (self.b / 'photo.jpg').write_bytes((self.a / 'original.jpg').read_bytes())
        self.assertEqual(self.library.scan('b')['cross_group_duplicate_count'], 0)

    def test_resume_retains_count_without_double_counting(self):
        for i in range(3):
            (self.b / f'{i}.jpg').write_bytes((self.a / 'original.jpg').read_bytes())
        stop = threading.Event()
        def progress(state):
            if state.get('processed', 0) >= 1:
                stop.set()
        first = self.library.scan('b', progress=progress, stopped=stop.is_set)
        self.assertEqual(first['status'], 'stopped')
        self.assertEqual(first['cross_group_duplicate_count'], 1)
        final = self.library.scan('b', mode='resume')
        self.assertEqual(final['cross_group_duplicate_count'], 3)
        self.assertEqual(duplicate_page(self.library, final['scan_id'])['total'], 3)
        self.assertEqual(self.library.scan('b')['cross_group_duplicate_count'], 3)

    def test_changed_hash_replaces_the_index_entry_and_missing_managed_file_is_explicit(self):
        first = self.library.merge()
        Path(first['operations'][0]['destination']).unlink()
        (self.b / 'photo.jpg').write_bytes((self.a / 'original.jpg').read_bytes())
        result = self.library.scan('b')
        match = duplicate_page(self.library, result['scan_id'])['items'][0]['matches'][0]
        self.assertFalse(match['managed_files'][0]['exists'])
        Image.new('RGB', (8, 8), 'green').save(self.b / 'photo.jpg')
        self.assertEqual(self.library.scan('b', full=True)['cross_group_duplicate_count'], 0)

    def test_read_only_paging_ignores_partial_final_line(self):
        (self.b / 'photo.jpg').write_bytes((self.a / 'original.jpg').read_bytes())
        result = self.library.scan('b')
        path = self.library.db / 'scans/sessions' / result['scan_id'] / 'results.jsonl'
        with path.open('ab') as stream:
            stream.write(b'{"partial":')
        before = path.read_bytes()
        self.assertEqual(duplicate_page(self.library, result['scan_id'])['total'], 1)
        self.assertEqual(path.read_bytes(), before)
        client = self.app.test_client()
        self.assertEqual(client.get(f'/api/scans/{result["scan_id"]}/duplicates?offset=-1').status_code, 400)
        self.assertEqual(client.get('/api/scans/missing/duplicates').status_code, 404)


if __name__ == '__main__':
    unittest.main()
