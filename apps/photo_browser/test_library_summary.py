import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app import create_app
from library import Library
from library_summary import LibrarySummary


class LibrarySummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'incoming'
        (self.source / 'nested').mkdir(parents=True)
        for index, directory in enumerate([self.source, self.source / 'nested']):
            Image.new('RGB', (8, 8), (index * 80, 40, 20)).save(directory / f'{index}.jpg')
        self.library = Library(self.root / 'db', self.root)
        self.library.save_config({'managed_root': str(self.root / 'managed'), 'scan_min_free_mb': 32,
                                  'sources': [{'source_id': 'photos', 'root': str(self.source), 'protocol': 'file',
                                               'category': 'family', 'owner_id': 'alice'}]})
        self.summary = LibrarySummary(self.library)

    def test_unscanned_registered_sources_still_visible(self):
        data = self.summary.snapshot()
        self.assertEqual(data['configured_source_count'], 1)
        self.assertEqual(data['catalog_source_count'], 0)
        self.assertEqual(data['totals']['media_count'], 0)
        self.assertEqual(data['current_chunk_count'], 0)
        self.assertEqual(data['sources'][0]['configured_category_ids'], ['family'])
        self.assertEqual(data['sources'][0]['owner_ids'], [])

    def test_source_category_owner_file_directory_and_size_totals(self):
        self.library.scan('photos')
        self.library.merge()
        data = self.summary.snapshot()
        total = data['totals']
        self.assertEqual(data['source_count'], 1)
        self.assertEqual(data['category_ids'], ['family'])
        self.assertEqual(data['owner_ids'], ['alice'])
        self.assertEqual(total['media_count'], 2)
        self.assertEqual(total['source_file_count'], 2)
        self.assertEqual(total['source_directory_count'], 2)
        self.assertEqual(total['managed_file_count'], 2)
        self.assertEqual(total['managed_directory_count'], 1)
        self.assertEqual(total['media_bytes'], sum(i['size_bytes'] for i in self.library.items()))
        self.assertEqual(len(data['groups']), 1)
        self.assertEqual(data['groups'][0]['source_id'], 'photos')

    def test_multiple_category_owner_combinations_are_not_collapsed_to_config(self):
        self.library.scan('photos')
        first = self.library.items()[0]
        self.library.edit([first['media_id']], {'category_id': 'work', 'owner_id': 'bob'})
        data = self.summary.snapshot()
        source = data['sources'][0]
        self.assertEqual(source['category_ids'], ['family', 'work'])
        self.assertEqual(source['owner_ids'], ['alice', 'bob'])
        self.assertEqual(source['configured_category_ids'], ['family'])
        self.assertEqual(source['configured_owner_ids'], ['alice'])
        self.assertEqual({(g['category_id'], g['owner_id']) for g in data['groups']}, {('family', 'alice'), ('work', 'bob')})
        self.assertTrue(all(g['media_count'] == 1 for g in data['groups']))

    def test_prior_generations_are_not_double_counted_and_cache_invalidates(self):
        self.library.scan('photos')
        old = self.summary.snapshot()
        self.assertFalse(old['cached'])
        with patch('library_summary.read_json', wraps=__import__('library_summary').read_json) as reading:
            self.assertTrue(self.summary.snapshot()['cached'])
            self.assertEqual(reading.call_count, 1)  # index only, no media chunks
        self.library.scan('photos')
        new = self.summary.snapshot()
        self.assertFalse(new['cached'])
        self.assertEqual(new['totals']['media_count'], 2)
        self.assertGreater(len(list((self.library.db / 'media').rglob('*.json'))), new['current_chunk_count'])

    def test_shared_copy_counted_once_and_multi_source_rows_can_overlap(self):
        self.library.scan('photos')
        # One logical item can have several recorded source locations.
        config = self.library.config()
        config['sources'].append({'source_id': 'mirror', 'protocol': 'http', 'root': 'https://example.invalid/photos'})
        self.library.save_config(config)
        items = self.library.items()
        items[0]['locations'].append({'role': 'source', 'source_id': 'mirror', 'protocol': 'http',
                                      'uri': 'https://example.invalid/photos/card.jpg', 'status': 'available'})
        self.library.commit(items)
        self.library.merge()
        with patch.object(self.library, 'remote_files', side_effect=AssertionError('no network')):
            data = self.summary.snapshot()
        self.assertEqual(data['catalog_source_count'], 2)
        self.assertEqual(data['totals']['media_count'], 2)
        self.assertEqual(data['totals']['source_file_count'], 3)
        self.assertEqual(data['totals']['managed_file_count'], 2)
        self.assertEqual(sum(s['media_count'] for s in data['sources']), 3)
        self.assertEqual(sum(s['managed_file_count'] for s in data['sources']), 3)

    def test_inactive_and_missing_originals_reported_separately(self):
        self.library.scan('photos')
        (self.source / '0.jpg').unlink()
        self.library.scan('photos')
        self.assertEqual(self.summary.snapshot()['totals']['missing_source_file_count'], 1)
        items = self.library.items()
        self.library.trash([items[0]['media_id']])
        data = self.summary.snapshot()
        self.assertEqual(data['inactive_media_count'], 1)
        self.assertEqual(data['totals']['media_count'], 1)
        self.assertEqual(data['sources'][0]['inactive_media_count'], 1)

    def test_unregistered_and_orphan_items_are_not_silently_lost(self):
        self.library.scan('photos')
        items = self.library.items()
        config = self.library.config()
        config['sources'] = []
        self.library.save_config(config)
        items[1]['locations'] = []
        self.library.commit(items)
        data = self.summary.snapshot()
        self.assertEqual(data['configured_source_count'], 0)
        self.assertEqual(data['source_count'], 1)
        self.assertFalse(data['sources'][0]['registered'])
        self.assertEqual(data['totals']['media_count'], 2)
        self.assertIn(None, [g['source_id'] for g in data['groups']])

    def test_force_refresh_rejects_missing_chunk_without_publishing_partial_counts(self):
        self.library.scan('photos')
        self.summary.snapshot()
        from library import read_json
        path = self.library.db / read_json(self.library.db / 'index.json')['chunks'][0]['path']
        path.unlink()
        with self.assertRaisesRegex(ValueError, '청크'):
            self.summary.snapshot(refresh=True)

    def test_api_is_authenticated_no_store_and_does_not_modify_database(self):
        self.library.scan('photos')
        client = create_app(self.root, self.root, self.library.db).test_client()
        before = {p: p.read_bytes() for p in self.library.db.rglob('*.json')}
        with patch.dict(os.environ, {'PHOTO_BROWSER_PASSWORD': 'test-password'}):
            self.assertEqual(client.get('/api/library-summary').status_code, 401)
            response = client.get('/api/library-summary?refresh=1', headers={'Authorization': 'Basic dXNlcjp0ZXN0LXBhc3N3b3Jk'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(response.json['totals']['media_count'], 2)
        self.assertEqual(before, {p: p.read_bytes() for p in self.library.db.rglob('*.json')})
        page = client.get('/').get_data(as_text=True)
        self.assertIn('<details id="library-summary"', page)
        self.assertIn('library_summary.js', page)


if __name__ == '__main__':
    unittest.main()
