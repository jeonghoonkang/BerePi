import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from db_usage import DirectoryUsage


class DirectoryUsageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'db'
        self.root.mkdir()
        self.usage = DirectoryUsage(self.root)

    def tearDown(self):
        if self.usage.worker:
            self.usage.worker.join(3)
        self.temp.cleanup()

    def refresh(self):
        self.usage.snapshot(force=True)
        self.usage.worker.join(3)
        return self.usage.snapshot()

    def test_counts_entire_db_including_old_generations_cache_and_hidden_files(self):
        for relative, size in [('index.json', 10), ('media/old.json', 20), ('cache/photo.jpg', 30),
                               ('downloads/photos.zip', 40), ('.write.lock', 1), ('empty.txt', 0)]:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'x' * size)
        (self.root.parent / 'managed.jpg').write_bytes(b'x' * 100)
        result = self.refresh()
        self.assertEqual(result['state'], 'ready')
        self.assertEqual(result['size_bytes'], 101)
        self.assertEqual(result['file_count'], 6)
        self.assertFalse(result['running'])
        self.assertIsNotNone(result['checked_at'])

    def test_polling_reuses_cache_and_explicit_refresh_counts_new_files(self):
        (self.root / 'a').write_bytes(b'123')
        self.assertEqual(self.refresh()['size_bytes'], 3)
        (self.root / 'b').write_bytes(b'4567')
        with patch.object(self.usage, 'measure') as measure:
            self.assertEqual(self.usage.snapshot()['size_bytes'], 3)
            measure.assert_not_called()
        self.assertEqual(self.refresh()['size_bytes'], 7)

    def test_empty_tree_and_unreadable_root_are_distinguished(self):
        self.assertEqual(self.refresh()['size_bytes'], 0)
        with patch('db_usage.os.scandir', side_effect=PermissionError('not readable')):
            result = self.refresh()
        self.assertEqual(result['state'], 'error')
        self.assertEqual(result['size_bytes'], 0)  # retained previous count
        other = DirectoryUsage(self.root)
        with patch('db_usage.os.scandir', side_effect=PermissionError('not readable')):
            other.measure()
        self.assertIsNone(other.value['size_bytes'])

    def test_unreadable_subdirectory_reports_partial_total(self):
        (self.root / 'good').write_bytes(b'123')
        (self.root / 'private').mkdir()
        import os
        original = os.scandir
        def scan(path):
            if Path(path).name == 'private':
                raise PermissionError('private')
            return original(path)
        with patch('db_usage.os.scandir', side_effect=scan):
            result = self.refresh()
        self.assertEqual(result['state'], 'partial')
        self.assertEqual(result['size_bytes'], 3)
        self.assertEqual(result['skipped'], 1)

    def test_link_targets_are_not_counted(self):
        outside = self.root.parent / 'outside'
        outside.mkdir()
        (outside / 'photo.jpg').write_bytes(b'x' * 100)
        try:
            (self.root / 'link').symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest('Symlinks unavailable')
        result = self.refresh()
        self.assertEqual(result['size_bytes'], 0)
        self.assertEqual(result['file_count'], 0)
        self.assertEqual(result['skipped'], 1)
