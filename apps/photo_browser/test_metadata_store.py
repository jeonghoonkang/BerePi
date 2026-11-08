import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from library import Library, atomic_json, read_json
from location_rescan import scan_missing_places
from place_lookup import place_from_address


class MetadataStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        source = self.root / 'source'
        source.mkdir()
        Image.new('RGB', (8, 8), 'red').save(source / 'photo.jpg')
        self.library = Library(self.root / 'db', self.root)
        self.library.save_config({'managed_root': str(self.root / 'managed'), 'scan_min_free_mb': 32,
                                  'sources': [{'source_id': 'photos', 'protocol': 'file', 'root': str(source),
                                               'category': 'family', 'owner_id': 'alice'}]})
        self.library.scan('photos')
        base = self.library.items()[0]
        items = []
        for i in range(205):
            item = copy.deepcopy(base)
            item['media_id'] = f'p{i:03}'
            items.append(item)
        self.library.commit(items)

    def tearDown(self):
        self.temp.cleanup()

    def manifest(self):
        return read_json(self.library.db / 'index.json')

    def test_only_affected_chunks_change_and_duplicates_are_reused(self):
        before = self.manifest()
        untouched = self.library.db / before['chunks'][1]['path']
        contents, modified = untouched.read_bytes(), untouched.stat().st_mtime_ns
        with patch.object(self.library, 'items', side_effect=AssertionError('Full catalog read')):
            self.library.edit(['p000', 'p001'], {'tags': ['holiday']})
        after = self.manifest()
        self.assertNotEqual(before['chunks'][0]['path'], after['chunks'][0]['path'])
        self.assertEqual(before['chunks'][1:], after['chunks'][1:])
        self.assertEqual(after['duplicates'], before['duplicates'])
        self.assertEqual(untouched.read_bytes(), contents)
        self.assertEqual(untouched.stat().st_mtime_ns, modified)
        self.assertEqual(after['active_facets']['tags'], ['holiday'])
        self.assertEqual(self.library.item('p001')['classification']['tags'], ['holiday'])
        self.assertEqual(self.library.item('p150')['classification']['tags'], [])
        self.library.edit(['p000', 'p001'], {'tags': []})
        self.assertEqual(self.manifest()['active_facets']['tags'], [])

    def test_noop_keeps_index_revision_and_files_unchanged(self):
        before = self.manifest()
        item = self.library.item('p000')
        with patch('metadata_store.atomic_json') as writes:
            self.library.edit(['p000'], {'tags': []})
        writes.assert_not_called()
        self.assertEqual(self.manifest(), before)
        self.assertEqual(self.library.item('p000')['revision'], item['revision'])

    def test_fresh_id_lookup_and_edit_do_not_read_unrelated_chunks(self):
        fresh = Library(self.library.db, self.root)
        target = self.library.db / self.manifest()['chunks'][0]['path']
        with patch('library.read_json', wraps=read_json) as reads:
            self.assertEqual(fresh.item('p000')['media_id'], 'p000')
        self.assertEqual([call.args[0] for call in reads.call_args_list], [self.library.db / 'index.json', target])
        with patch('metadata_store.read_json', wraps=read_json) as reads:
            fresh.edit(['p001'], {'tags': ['new']})
        self.assertEqual([call.args[0] for call in reads.call_args_list], [self.library.db / 'index.json', target])

    def test_multi_chunk_commit_failure_preserves_previous_view(self):
        before = self.manifest()
        def write(path, data):
            if path == self.library.db / 'index.json':
                raise OSError('simulated index publication failure')
            atomic_json(path, data)
        with patch('metadata_store.atomic_json', side_effect=write), self.assertRaises(OSError):
            self.library.edit(['p000', 'p150'], {'tags': ['unpublished']})
        self.assertEqual(self.manifest(), before)
        self.assertEqual(self.library.item('p000')['classification']['tags'], [])
        self.assertEqual(self.library.item('p150')['classification']['tags'], [])

    def test_two_chunks_change_without_shifting_membership(self):
        before = self.manifest()
        self.library.edit(['p000', 'p150'], {'tags': ['two pages']})
        after = self.manifest()
        self.assertEqual(sum(a['path'] != b['path'] for a, b in zip(before['chunks'], after['chunks'])), 2)
        self.assertEqual([c['media_ids'] for c in before['chunks']], [c['media_ids'] for c in after['chunks']])

    def test_inactive_tags_do_not_reappear_in_active_facets(self):
        items = self.library.items()
        items[0]['classification']['tags'] = ['last-active-tag']
        items[-1]['classification']['tags'] = ['inactive-only']
        items[-1]['lifecycle']['status'] = 'trashed'
        self.library.commit(items)
        self.library.edit(['p000'], {'tags': []})
        self.assertEqual(self.library.facets()['tags'], [])
        self.assertEqual(self.library.item('p204')['classification']['tags'], ['inactive-only'])

    def test_partial_writer_rejects_gps_changes(self):
        with self.library.writing(), self.assertRaises(ValueError):
            self.library._patch_metadata({'p000': {'location': {'latitude': 0, 'longitude': 0}}})

    def test_legacy_catalog_migrates_lookup_metadata_without_rewriting_other_pages(self):
        before = self.manifest()
        for entry in before['chunks']:
            entry.pop('media_ids')
            entry.pop('active_facets')
        atomic_json(self.library.db / 'index.json', before)
        legacy = Library(self.library.db, self.root)
        legacy.edit(['p000'], {'tags': ['migrated']})
        after = self.manifest()
        self.assertTrue(all('media_ids' in c and 'active_facets' in c for c in after['chunks']))
        self.assertEqual(before['chunks'][1]['path'], after['chunks'][1]['path'])
        restarted = Library(self.library.db, self.root)
        with patch('library.read_json', wraps=read_json) as reads:
            restarted.item('p150')
        self.assertEqual(len(reads.call_args_list), 2)

    def prepare_places(self):
        items = self.library.items()
        for item in items:
            item['capture']['location'] = {'latitude': 37.5, 'longitude': 127.1}
            item['capture']['place'] = place_from_address({'country': 'South Korea'})
        items[0]['capture'].pop('place')
        self.library.commit(items)

    def test_nominatim_updates_only_the_affected_page(self):
        self.prepare_places()
        before = self.manifest()
        place = place_from_address({'city': 'Seoul'})
        with patch.dict(os.environ, {'PHOTO_BROWSER_REVERSE_GEOCODER_URL': 'http://127.0.0.1:8080/reverse'}), \
                patch('location_rescan.PlaceLookup.lookup', return_value=place), \
                patch.object(self.library, 'commit', side_effect=AssertionError('Full catalog write')):
            result = scan_missing_places(self.library, lambda _: None, lambda: False)
        after = self.manifest()
        self.assertEqual(result['updated'], 1)
        self.assertEqual(after['chunks'][1:], before['chunks'][1:])
        self.assertEqual(after['duplicates'], before['duplicates'])
        self.assertIn('Seoul', self.library.item('p000')['classification']['location_tags'])

    def test_fast_merge_with_only_place_updates_uses_partial_commit(self):
        self.prepare_places()
        self.library.merge(ids=['p000'])
        before = self.manifest()
        place = place_from_address({'city': 'Seoul'})
        with patch.dict(os.environ, {'PHOTO_BROWSER_REVERSE_GEOCODER_URL': 'http://127.0.0.1:8080/reverse'}), \
                patch('place_lookup.PlaceLookup.lookup', return_value=place), \
                patch.object(self.library, 'commit', side_effect=AssertionError('Full catalog write')):
            result = self.library.merge(ids=['p000'])
        self.assertEqual(result['fast_skipped_count'], 1)
        self.assertEqual(self.manifest()['chunks'][1:], before['chunks'][1:])
        self.assertIn('Seoul', self.library.item('p000')['classification']['location_tags'])


if __name__ == '__main__':
    unittest.main()
