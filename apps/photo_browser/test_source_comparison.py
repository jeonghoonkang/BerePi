import copy
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from source_comparison import SourceComparison
from test_support import create_app


class SourceComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.app = create_app(self.root, self.root, self.root / 'db')
        self.library = self.app.extensions['photo_library']
        self.client = self.app.test_client()
        self.headers = {'X-Photo-Browser': '1'}
        sources = []
        for sid in ('a', 'b'):
            folder = self.root / sid
            folder.mkdir()
            for index, color in enumerate(('red', 'blue')):
                Image.new('RGB', (8, 8), color).save(folder / f'{index}.jpg')
            sources.append({'source_id': sid, 'root': str(folder), 'protocol': 'file', 'category': 'photo_box', 'owner_id': 'alice'})
        self.library.save_config({'managed_root': str(self.root / 'managed'), 'scan_min_free_mb': 32, 'sources': sources})
        for sid in ('a', 'b'):
            self.library.scan(sid)
        self.library.merge()
        self.store = SourceComparison(self.library)
        self.left = {'source_id': 'a', 'category': 'photo_box'}
        self.right = {'source_id': 'b', 'category': 'photo_box'}

    def tearDown(self):
        self.temp.cleanup()

    def compare(self):
        result = self.store.compare(self.left, self.right)
        return self.store.page(result['comparison_id'])

    def item(self, items, source, name='0.jpg'):
        return next(item for item in items if item['name'] == name and item['locations'][0]['source_id'] == source)

    def test_identical_content_different_originals_shared_managed_no_media_reads(self):
        before = self.library.items()
        with patch('library.digest', side_effect=AssertionError('Do not rehash photos')), patch.object(self.library, 'materialize', side_effect=AssertionError('No originals')):
            result = self.compare()
        self.assertTrue(result['same_contents'])
        self.assertTrue(result['same_multiplicity'])
        self.assertEqual(result['counts']['same'], 2)
        self.assertEqual(result['shared_source_paths'], 0)
        self.assertEqual(result['shared_managed_paths'], 2)
        self.assertEqual(result['shared_media_ids'], 0)
        self.assertEqual(self.library.items(), before)

    def test_duplicate_db_entries_and_missing_originals_are_visible(self):
        items = self.library.items()
        for name in ('0.jpg', '1.jpg'):
            source = self.item(items, 'a', name)['locations'][0]
            old = self.item(items, 'b', name)['locations'][0]
            old.update(path=source['path'], uri=source['uri'], status='missing')
        duplicate = copy.deepcopy(self.item(items, 'a'))
        duplicate['media_id'] = 'extra'
        self.library.commit(items + [duplicate])
        result = self.compare()
        self.assertEqual(result['shared_source_paths'], 2)
        self.assertEqual(result['missing_right_items'], 2)
        self.assertTrue(result['same_contents'])
        self.assertFalse(result['same_multiplicity'])
        self.assertEqual((result['left_items'], result['right_items']), (3, 2))

    def test_same_path_different_hash_is_a_conflict(self):
        items = self.library.items()
        a, b = self.item(items, 'a'), self.item(items, 'b')
        b['locations'][0].update(path=a['locations'][0]['path'], uri=a['locations'][0]['uri'])
        b['sha256'] = '1' * 64
        self.library.commit(items)
        result = self.compare()
        self.assertFalse(result['same_contents'])
        self.assertEqual(result['conflicting_source_paths'], 1)
        self.assertEqual(result['counts']['left_only'], 1)
        self.assertEqual(result['counts']['right_only'], 1)
        conflict = self.store.page(result['comparison_id'], 'conflict')
        self.assertEqual(conflict['total'], 2)

    def test_missing_hash_never_proves_equality_and_category_scope_is_exact(self):
        items = self.library.items()
        self.item(items, 'b')['sha256'] = None
        self.item(items, 'b', '1.jpg')['classification']['category_id'] = 'other'
        self.library.commit(items)
        result = self.compare()
        self.assertFalse(result['same_contents'])
        self.assertEqual(result['counts']['unknown'], 1)
        self.assertEqual(result['right_items'], 1)
        self.right['category'] = 'empty'
        result = self.compare()
        self.assertEqual(result['right_items'], 0)
        self.assertFalse(result['same_contents'])

    def test_shared_item_and_inactive_items_and_validation(self):
        items = self.library.items()
        a = self.item(items, 'a')
        a['locations'].append({**a['locations'][0], 'source_id': 'b'})
        self.item(items, 'b')['lifecycle']['status'] = 'inactive'
        self.library.commit(items)
        result = self.compare()
        self.assertEqual(result['shared_media_ids'], 1)
        self.assertTrue(result['same_contents'])
        for invalid in (None, {}, {'source_id': '../outside'}):
            with self.assertRaises(ValueError):
                self.store.compare(invalid, self.right)
        with self.assertRaises(ValueError):
            self.store.compare(self.left, self.left)
        with self.assertRaises(ValueError):
            self.store.page('../outside')

    def test_unknown_hash_at_shared_path_is_not_reported_as_known_conflict(self):
        items = self.library.items()
        a, b = self.item(items, 'a'), self.item(items, 'b')
        b['locations'][0].update(path=a['locations'][0]['path'], uri=a['locations'][0]['uri'])
        unknown = copy.deepcopy(b)
        unknown.update(media_id='unknown', sha256=None)
        self.library.commit(items + [unknown])
        result = self.compare()
        self.assertEqual(result['shared_source_paths'], 1)
        self.assertEqual(result['conflicting_source_paths'], 0)
        self.assertFalse(result['same_contents'])

    def test_same_hash_different_size_is_not_equal(self):
        items = self.library.items()
        self.item(items, 'b')['size_bytes'] += 1
        self.library.commit(items)
        result = self.compare()
        self.assertFalse(result['same_contents'])
        self.assertEqual(result['counts']['left_only'], 1)
        self.assertEqual(result['counts']['right_only'], 1)

    def test_background_api_pagination_download_and_entry_limits(self):
        self.assertEqual(self.client.post('/api/source-comparisons', json={'left': self.left, 'right': self.right}).status_code, 403)
        response = self.client.post('/api/source-comparisons', json={'left': self.left, 'right': self.right}, headers=self.headers)
        self.assertEqual(response.status_code, 202)
        for _ in range(500):
            status = self.client.get('/api/jobs/' + response.json['job_id']).json
            if status['status'] not in {'running', 'queued', 'stopping'}:
                break
            time.sleep(0.01)
        self.assertEqual(status['status'], 'completed', status)
        cid = status['result']['comparison_id']
        result = self.client.get(f'/api/source-comparisons/{cid}?limit=1').json
        self.assertEqual(result['total'], 2)
        self.assertEqual(len(result['rows']), 1)
        self.assertEqual(self.client.get(f'/api/source-comparisons/{cid}?status=left_only').json['total'], 0)
        self.assertEqual(self.client.get(f'/api/source-comparisons/{cid}?status=invalid').status_code, 400)
        download = self.client.get(f'/api/source-comparisons/{cid}/download')
        self.assertEqual(download.status_code, 200)
        self.assertIn('attachment', download.headers['Content-Disposition'])
        download.close()
        items = self.library.items()
        item = self.item(items, 'a')
        copies = [{**copy.deepcopy(item), 'media_id': f'copy{n}'} for n in range(30)]
        self.library.commit(items + copies)
        report = self.compare()
        row = next(row for row in report['rows'] if row['left_count'] > 20)
        self.assertEqual(len(row['left']), 20)
        self.assertEqual(row['left_count'], 31)


if __name__ == '__main__':
    unittest.main()
