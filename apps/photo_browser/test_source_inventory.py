import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from library import Library
from source_inventory import compare_source_inventory, inventory_size, profile


class SourceInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.a, self.b = self.root / 'a', self.root / 'b'
        self.a.mkdir(); self.b.mkdir()
        self.library = Library(self.root / 'db', self.root)
        self.sources = [{'source_id': 'a', 'protocol': 'file', 'root': str(self.a), 'category': 'family', 'owner_id': 'alice'},
                        {'source_id': 'b', 'protocol': 'file', 'root': str(self.b), 'category': 'travel', 'owner_id': 'bob'}]
        self.library.save_config({'managed_root': str(self.root / 'managed'), 'scan_min_free_mb': 32, 'sources': self.sources})
        Image.new('RGB', (8, 8), 'red').save(self.a / 'photo.jpg')
        self.library.scan('a')

    def tearDown(self):
        self.temp.cleanup()

    def test_identical_layout_is_a_candidate_and_still_checks_file_contents(self):
        (self.b / 'renamed.jpg').write_bytes((self.a / 'photo.jpg').read_bytes())
        from library import digest
        with patch('scan_engine.digest', wraps=digest) as hashing:
            result = self.library.scan('b')
        data = result['source_inventory']
        self.assertEqual(data['same_layout_count'], 1)
        self.assertEqual(data['comparisons'][0]['status'], 'same_layout_candidate')
        self.assertEqual(data['current']['file_count'], 1)
        self.assertEqual(data['current']['total_bytes'], (self.b / 'renamed.jpg').stat().st_size)
        self.assertEqual(result['cross_group_duplicate_count'], 1)
        hashing.assert_called_once()

    def test_different_directory_structure_keeps_checking_overlap(self):
        (self.b / 'nested').mkdir()
        (self.b / 'nested/photo.jpg').write_bytes((self.a / 'photo.jpg').read_bytes())
        result = self.library.scan('b')
        data = result['source_inventory']
        self.assertEqual(data['different_source_count'], 1)
        self.assertEqual(data['current']['file_count'], data['comparisons'][0]['file_count'])
        self.assertEqual(data['current']['total_bytes'], data['comparisons'][0]['total_bytes'])
        self.assertNotEqual(data['current']['structure_fingerprint'], data['comparisons'][0]['structure_fingerprint'])
        self.assertEqual(result['cross_group_duplicate_count'], 1)

    def test_same_count_and_size_never_prove_identical_bytes(self):
        first = self.a / 'photo.jpg'
        original = first.read_bytes()
        other = bytearray(original)
        other[-1] ^= 1
        (self.b / 'photo.jpg').write_bytes(other)
        result = self.library.scan('b')
        self.assertEqual(result['source_inventory']['same_layout_count'], 1)
        self.assertEqual(result['cross_group_duplicate_count'], 0)

    def test_unknown_remote_size_is_not_classified_as_different_source(self):
        remote = {'source_id': 'remote', 'protocol': 'http', 'root': 'https://example.com/photos'}
        data = compare_source_inventory(self.library, remote, [{'uri': 'https://example.com/photos/one.jpg', 'info': {}}], self.library.items())
        self.assertIsNone(data['current']['total_bytes'])
        self.assertTrue(all(row['status'] == 'insufficient_inventory' for row in data['comparisons']))
        self.assertEqual(inventory_size(self.library, remote, {'size': '0'}), 0)

    def test_inventory_metadata_is_reused_without_stat_or_source_reads(self):
        source = self.sources[1]
        entries = [{'uri': (self.b / 'photo.jpg').as_uri(), 'info': {'path': str(self.b / 'photo.jpg')}, 'size_bytes': 100}]
        with patch('source_inventory.inventory_size', side_effect=AssertionError('unnecessary stat')):
            data = compare_source_inventory(self.library, source, entries, self.library.items())
        self.assertEqual(data['current']['total_bytes'], 100)

    def test_profile_is_stable_across_roots_and_traversal_order(self):
        a = profile(self.sources[0], [((self.a / 'x/one.jpg').as_uri(), 10), ((self.a / 'two.jpg').as_uri(), 20)])
        b = profile(self.sources[1], [((self.b / 'different.jpg').as_uri(), 20), ((self.b / 'x/name.jpg').as_uri(), 10)])
        self.assertEqual(a, b)


if __name__ == '__main__':
    unittest.main()
