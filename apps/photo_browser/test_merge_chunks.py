import copy
from pathlib import Path
import unittest
from unittest.mock import patch

from library import atomic_json, read_json
import test_metadata_store


class MergeChunkTests(unittest.TestCase):
    setUp = test_metadata_store.MetadataStoreTests.setUp
    tearDown = test_metadata_store.MetadataStoreTests.tearDown
    manifest = test_metadata_store.MetadataStoreTests.manifest

    def fake_location(self, item):
        item = copy.deepcopy(item)
        path = Path(self.library.config()['managed_root']) / 'new.jpg'
        item['locations'].append({'role': 'managed', 'protocol': 'file', 'path': str(path),
                                  'uri': path.as_uri(), 'status': 'available'})
        return item

    def test_sparse_merge_only_replaces_affected_pages_and_reuses_duplicates(self):
        before = self.manifest()
        untouched = self.library.db / before['chunks'][2]['path']
        contents, mtime = untouched.read_bytes(), untouched.stat().st_mtime_ns
        duplicates = set((self.library.db / 'duplicates').glob('*.json'))
        with patch.object(self.library, 'commit', side_effect=AssertionError('Full catalog write')), \
                patch('metadata_store.read_json', wraps=read_json) as reads:
            result = self.library.merge(ids=['p000', 'p100'])
        self.assertEqual(result['status'], 'completed')
        after = self.manifest()
        self.assertNotEqual(before['chunks'][0]['path'], after['chunks'][0]['path'])
        self.assertNotEqual(before['chunks'][1]['path'], after['chunks'][1]['path'])
        self.assertEqual(before['chunks'][2], after['chunks'][2])
        self.assertNotIn(untouched, [call.args[0] for call in reads.call_args_list])
        self.assertEqual(untouched.read_bytes(), contents)
        self.assertEqual(untouched.stat().st_mtime_ns, mtime)
        self.assertEqual(after['duplicates'], before['duplicates'])
        self.assertEqual(set((self.library.db / 'duplicates').glob('*.json')), duplicates)

    def test_checkpoint_writes_scale_with_touched_pages_and_repeat_is_noop(self):
        before_files = set((self.library.db / 'media').rglob('*.json'))
        with patch.object(self.library, 'commit', side_effect=AssertionError('Full catalog write')):
            self.library.merge()
        added = set((self.library.db / 'media').rglob('*.json')) - before_files
        # 205 items: four checkpoints for each 100-item page, then one for 5.
        self.assertEqual(len(added), 9)
        before_index = (self.library.db / 'index.json').read_bytes()
        before_files = set((self.library.db / 'media').rglob('*.json'))
        with patch.object(self.library, 'commit', side_effect=AssertionError('Full catalog write')):
            result = self.library.merge()
        self.assertEqual(result['fast_skipped_count'], 205)
        self.assertEqual((self.library.db / 'index.json').read_bytes(), before_index)
        self.assertEqual(set((self.library.db / 'media').rglob('*.json')), before_files)

    def test_stop_and_resume_publish_each_changed_chunk_only(self):
        before = self.manifest()
        stop = [False]
        def progress(value):
            if value.get('phase') == 'merging' and value.get('processed', 0) >= 1:
                stop[0] = True
        with patch.object(self.library, 'commit', side_effect=AssertionError('Full catalog write')):
            first = self.library.merge(ids=['p000', 'p100'], progress=progress, stopped=lambda: stop[0])
            stopped = self.manifest()
            self.assertEqual(first['status'], 'stopped')
            self.assertEqual(stopped['chunks'][1:], before['chunks'][1:])
            self.assertTrue(any(loc['role'] == 'managed' for loc in self.library.item('p000')['locations']))
            self.library.merge(resume=first['merge_id'])
        after = self.manifest()
        self.assertEqual(after['chunks'][0], stopped['chunks'][0])
        self.assertNotEqual(after['chunks'][1]['path'], stopped['chunks'][1]['path'])
        self.assertEqual(after['chunks'][2], stopped['chunks'][2])

    def test_noop_updates_do_not_create_chunks_or_touch_index(self):
        before = (self.library.db / 'index.json').read_bytes()
        item = self.library.item('p000')
        with self.library.writing(), patch('metadata_store.atomic_json') as writes:
            self.assertEqual(self.library._patch_merge_items({'p000': item}), 0)
        writes.assert_not_called()
        self.assertEqual((self.library.db / 'index.json').read_bytes(), before)

    def test_failed_publication_keeps_the_previous_complete_view(self):
        before = self.manifest()
        changes = {mid: self.fake_location(self.library.item(mid)) for mid in ('p000', 'p100')}
        def fail_index(path, value):
            if path.name == 'index.json':
                raise OSError('simulated index publication failure')
            return atomic_json(path, value)
        with self.library.writing(), patch('metadata_store.atomic_json', side_effect=fail_index):
            with self.assertRaises(OSError): self.library._patch_merge_items(changes)
        self.assertEqual(self.manifest(), before)
        self.assertFalse(any(loc['role'] == 'managed' for loc in self.library.item('p000')['locations']))
        with self.library.writing(): self.library._patch_merge_items(changes)
        self.assertTrue(any(loc['role'] == 'managed' for loc in self.library.item('p000')['locations']))

    def test_failed_merge_checkpoint_can_resume_with_existing_verified_copies(self):
        before = self.manifest()
        def fail_index(path, value):
            if path.name == 'index.json': raise OSError('simulated checkpoint failure')
            return atomic_json(path, value)
        with patch('metadata_store.atomic_json', side_effect=fail_index):
            with self.assertRaises(OSError): self.library.merge(ids=['p000', 'p100'])
        self.assertEqual(self.manifest(), before)
        session = read_json(next((self.library.db / 'merges').glob('*.json')))
        self.assertEqual(session['processed'], 0)
        with patch.object(self.library, 'commit', side_effect=AssertionError('Full catalog write')):
            result = self.library.merge(resume=session['merge_id'])
        self.assertEqual(result['status'], 'completed')
        self.assertTrue(all(operation['status'] == 'reused' for operation in result['operations']))
        self.assertEqual(self.manifest()['chunks'][2], before['chunks'][2])

    def test_content_grouping_source_and_state_changes_are_rejected(self):
        for field in ('sha256', 'category', 'date', 'source', 'state'):
            item = self.library.item('p000')
            if field == 'sha256': item['sha256'] = '1' * 64
            elif field == 'category': item['classification']['category_id'] = 'new'
            elif field == 'date': item['capture']['date_key'] = '2020-01-01'
            elif field == 'source': item['locations'][0]['source_id'] = 'changed'
            else: item['lifecycle']['status'] = 'trashed'
            with self.subTest(field=field), self.library.writing(), self.assertRaises(ValueError):
                self.library._patch_merge_items({'p000': item})

    def test_space_estimate_uses_touched_pages_and_skips_unchanged_pages(self):
        items = self.library.items()
        root = Path(self.library.config()['managed_root'])
        estimate = self.library.merge_space(root, items, [items[0]], lambda value: None)
        self.assertEqual(estimate['db_estimate_model'], 'copy_on_write_chunks')
        self.assertEqual(estimate['estimated_touched_chunks'], 1)
        self.assertEqual(estimate['estimated_chunk_writes'], 2)
        self.library.merge(ids=['p000'])
        item = self.library.item('p000')
        estimate = self.library.merge_space(root, self.library.items(), [item], lambda value: None)
        self.assertEqual(estimate['estimated_chunk_writes'], 0)


if __name__ == '__main__':
    unittest.main()
