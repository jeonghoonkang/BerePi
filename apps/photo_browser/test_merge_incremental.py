import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from library import Library, digest
from merge_status import merge_status


class IncrementalMergeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'source'
        self.source.mkdir()
        self.library = Library(self.root / 'db', self.root)
        self.library.save_config({'managed_root': str(self.root / 'managed'), 'scan_min_free_mb': 32,
                                  'sources': [{'source_id': 'photos', 'protocol': 'file', 'root': str(self.source),
                                               'category': 'family', 'owner_id': 'alice'}]})

    def tearDown(self):
        self.temp.cleanup()

    def photo(self, name, color):
        Image.new('RGB', (8, 8), color).save(self.source / name)

    def baseline(self):
        self.photo('a.jpg', 'red')
        self.library.scan('photos')
        return Path(self.library.merge()['operations'][0]['destination'])

    def test_unchanged_merge_reads_no_content_and_writes_no_catalog_generation(self):
        target = self.baseline()
        with patch('library.digest', side_effect=AssertionError('Unexpected content read')), \
                patch('library.shutil.copy2', side_effect=AssertionError('Unexpected copy')), \
                patch.object(self.library, 'commit') as commit:
            result = self.library.merge()
        commit.assert_not_called()
        self.assertEqual(result['operations'][0]['destination'], str(target))
        self.assertEqual(result['fast_skipped_count'], 1)
        self.assertTrue(result['operations'][0]['fast_skipped'])
        self.assertEqual(result['history_report']['summary']['fast_skipped_count'], 1)
        self.assertEqual(merge_status(self.library.db)['items'][0]['fast_skipped_count'], 1)

    def test_mixed_source_only_copies_new_changed_and_missing_files(self):
        for name, color in [('a.jpg', 'red'), ('b.jpg', 'blue'), ('c.jpg', 'green')]:
            self.photo(name, color)
        self.library.scan('photos')
        first = self.library.merge()
        paths = {Path(op['destination']).name: Path(op['destination']) for op in first['operations']}
        paths['c.jpg'].unlink()
        self.photo('b.jpg', 'yellow')
        stat = (self.source / 'b.jpg').stat()
        os.utime(self.source / 'b.jpg', ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
        self.photo('d.jpg', 'purple')
        self.library.scan('photos')
        with patch('library.digest', wraps=digest) as hashing:
            result = self.library.merge()
        self.assertEqual(result['fast_skipped_count'], 1)
        self.assertEqual(sum(op['status'] == 'copied' for op in result['operations']), 3)
        self.assertNotIn(paths['a.jpg'], [call.args[0] for call in hashing.call_args_list])
        for op in result['operations']:
            item = self.library.item(op['media_id'])
            self.assertEqual(digest(Path(op['destination'])), item['sha256'])

    def test_mtime_change_requires_hash_verification_once(self):
        target = self.baseline()
        stat = target.stat()
        os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1))
        with patch('library.digest', wraps=digest) as hashing:
            result = self.library.merge()
        self.assertEqual(result['fast_skipped_count'], 0)
        self.assertEqual(result['operations'][0]['status'], 'reused')
        self.assertEqual([call.args[0] for call in hashing.call_args_list], [target])
        self.assertEqual(self.library.merge()['fast_skipped_count'], 1)

    def test_legacy_record_is_verified_before_becoming_eligible(self):
        target = self.baseline()
        items = self.library.items()
        for location in items[0]['locations']:
            location.pop('merge_verification', None)
        self.library.commit(items)
        with patch('library.digest', wraps=digest) as hashing:
            result = self.library.merge()
        self.assertEqual(result['fast_skipped_count'], 0)
        self.assertEqual([call.args[0] for call in hashing.call_args_list], [target])
        self.assertEqual(self.library.merge()['fast_skipped_count'], 1)

    def test_category_change_copies_to_the_new_path(self):
        self.baseline()
        item = self.library.items()[0]
        self.library.edit([item['media_id']], {'category_id': 'travel'})
        result = self.library.merge()
        self.assertEqual(result['fast_skipped_count'], 0)
        self.assertEqual(result['operations'][0]['status'], 'copied')
        self.assertIn('/travel/', result['operations'][0]['destination'])

    def test_collision_suffix_can_be_skipped_without_hashing_occupied_names(self):
        self.photo('a.jpg', 'red')
        self.library.scan('photos')
        target = self.library.merge_target(Path(self.library.config()['managed_root']), self.library.items()[0])
        target.parent.mkdir(parents=True)
        target.write_bytes(b'other content')
        result = self.library.merge()
        self.assertIn('_중복', result['operations'][0]['destination'])
        with patch('library.digest', side_effect=AssertionError('Unexpected collision rehash')):
            result = self.library.merge()
        self.assertEqual(result['fast_skipped_count'], 1)

    def test_changed_target_is_preserved_and_a_valid_copy_is_created(self):
        target = self.baseline()
        target.write_bytes(b'corrupted')
        result = self.library.merge()
        self.assertEqual(result['fast_skipped_count'], 0)
        self.assertEqual(result['operations'][0]['status'], 'copied')
        self.assertNotEqual(result['operations'][0]['destination'], str(target))
        self.assertEqual(target.read_bytes(), b'corrupted')


if __name__ == '__main__':
    unittest.main()
