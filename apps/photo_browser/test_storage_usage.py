from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from library import Library
from storage_usage import StorageUsage, human_bytes


class StorageUsageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'sources'; (self.source / 'nested').mkdir(parents=True)
        (self.source / 'first.bin').write_bytes(b'x' * 10)
        (self.source / 'nested' / 'second.bin').write_bytes(b'x' * 20)
        self.library = Library(self.root / 'db', self.root)
        config = self.library.config()
        config.update(scan_min_free_mb=32, sources=[{'source_id': 'parent', 'protocol': 'file', 'root': str(self.source)},
                                                  {'source_id': 'child', 'protocol': 'file', 'root': str(self.source / 'nested')}])
        self.library.save_config(config)
        self.managed = Path(config['managed_root'])
        metadata = [path for path in self.managed.rglob('*') if path.is_file()]
        self.managed_base_bytes = sum(path.stat().st_size for path in metadata)
        self.managed_base_count = len(metadata)
        (self.managed / 'photo.bin').write_bytes(b'x' * 15)
        self.usage = StorageUsage(self.library.db, self.root)

    def test_counts_entire_db_source_union_and_managed_trash(self):
        (self.library.db / 'other.log').write_bytes(b'x' * 100)
        (self.managed / '.trash').mkdir()
        (self.managed / '.trash' / 'old.bin').write_bytes(b'x' * 25)
        expected_db = sum(path.stat().st_size for path in self.library.db.rglob('*') if path.is_file())
        result = self.usage.measure()
        self.assertEqual(result['categories']['db']['logical_bytes'], expected_db)
        self.assertEqual(result['categories']['sources']['logical_bytes'], 30)
        self.assertEqual(result['categories']['managed']['logical_bytes'], self.managed_base_bytes + 40)
        self.assertEqual(len(result['volumes']), 1)
        self.assertEqual(set(result['volumes'][0]['roles']), {'db', 'sources', 'managed'})

    def test_hardlinks_are_counted_once_but_paths_remain_counted(self):
        try: os.link(self.managed / 'photo.bin', self.managed / 'alias.bin')
        except OSError: self.skipTest('Hard links unavailable')
        result = self.usage.measure()['categories']['managed']
        self.assertEqual((result['logical_bytes'], result['file_count'], result['unique_file_count']),
                         (self.managed_base_bytes + 15, self.managed_base_count + 2, self.managed_base_count + 1))
        self.assertGreaterEqual(result['allocated_bytes'], 0)

    def test_source_parent_does_not_include_db_or_managed_bytes(self):
        config = self.library.config()
        config['sources'] = [{'source_id': 'all', 'protocol': 'file', 'root': str(self.root)}]
        self.library.save_config(config)
        self.assertEqual(self.usage.measure()['categories']['sources']['logical_bytes'], 30)

    def test_same_filesystem_capacity_is_queried_once_and_not_summed(self):
        with patch('storage_usage.shutil.disk_usage', return_value=SimpleNamespace(total=1000, used=600, free=300)) as query:
            volumes, errors = self.usage.disks()
        self.assertEqual(len(volumes), 1)
        self.assertEqual((volumes[0]['total_bytes'], volumes[0]['free_bytes'], volumes[0]['used_percent']), (1000, 300, 60))
        query.assert_called_once()
        self.assertEqual(errors, [])

    def test_missing_and_remote_sources_are_unknown_not_zero(self):
        config = self.library.config()
        config['sources'] = [{'source_id': 'missing', 'protocol': 'file', 'root': str(self.root / 'missing')},
                             {'source_id': 'remote', 'protocol': 'http', 'root': 'https://example.test/photos.json'}]
        self.library.save_config(config)
        result = self.usage.measure()
        self.assertEqual(result['state'], 'partial')
        self.assertIsNone(result['categories']['sources']['logical_bytes'])
        self.assertEqual(len(result['errors']), 2)

    def test_symlinks_are_not_followed_and_failures_are_visible(self):
        (self.source / 'link').symlink_to(self.managed, target_is_directory=True)
        result = self.usage.measure()['categories']['sources']
        self.assertEqual(result['logical_bytes'], 30)
        self.assertEqual(result['state'], 'partial')
        self.assertEqual(result['skipped'], 1)

    def test_offline_after_cached_measurement_keeps_date_but_marks_partial(self):
        self.usage.measure()
        (self.source / 'first.bin').unlink()
        (self.source / 'nested' / 'second.bin').unlink()
        (self.source / 'nested').rmdir(); self.source.rmdir()
        current = self.usage.current()
        self.assertEqual(current['state'], 'partial')
        self.assertEqual(current['categories']['sources']['logical_bytes'], 30)
        self.assertIsNotNone(current['checked_at'])
        self.assertTrue(current['errors'])

    def test_snapshot_is_nonblocking_and_refreshes_in_background(self):
        entered, release = threading.Event(), threading.Event()
        original = os.scandir
        def scan(path):
            if Path(path) == self.source:
                entered.set(); release.wait(3)
            return original(path)
        with patch('storage_usage.os.scandir', side_effect=scan):
            start = time.monotonic()
            result = self.usage.snapshot()
            self.assertLess(time.monotonic() - start, 1)
            self.assertTrue(result['running'])
            try: self.assertTrue(entered.wait(1))
            finally: release.set(); self.usage.worker.join(3)
        self.assertEqual(self.usage.snapshot()['categories']['sources']['logical_bytes'], 30)
        with patch.object(self.usage, 'refresh') as refresh:
            self.usage.snapshot(); refresh.assert_not_called()

    def test_persistent_cache_and_cli_stderr_leave_json_stdout_valid(self):
        self.usage.measure()
        from cli import main
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            self.assertEqual(main(['--db', str(self.library.db), '--root', str(self.root), 'config']), 0)
        self.assertIn('config', json.loads(output.getvalue()))
        self.assertIn('저장 공간 현황', errors.getvalue())
        self.assertIn('원본 소스: 파일 30.00 B', errors.getvalue())
        self.assertIn('사용 가능', errors.getvalue())
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(io.StringIO()):
            self.assertEqual(main(['--db', str(self.library.db), '--root', str(self.root), 'storage-usage', '--refresh']), 0)
        self.assertEqual(json.loads(output.getvalue())['categories']['sources']['logical_bytes'], 30)

    def test_api_requires_login_and_returns_background_snapshot(self):
        from test_support import create_app
        app = create_app(self.root, self.root, self.library.db)
        response = app.test_client().get('/api/storage-usage')
        self.assertEqual(response.status_code, 200)
        worker = app.extensions['storage_usage'].worker
        if worker: worker.join(3)
        self.assertEqual(app.test_client().get('/api/storage-usage').json['categories']['sources']['logical_bytes'], 30)
        from app import create_app as real_app
        with patch.dict(os.environ, {'PHOTO_BROWSER_PASSWORD': 'test-only-password'}):
            self.assertEqual(real_app(self.root, self.root, self.library.db).test_client().get('/api/storage-usage').status_code, 401)

    def test_units_do_not_confuse_unknown_and_empty(self):
        self.assertEqual(human_bytes(None), '미집계')
        self.assertEqual(human_bytes(0), '0.00 B')
        self.assertEqual(human_bytes(1024), '1.00 KiB')


if __name__ == '__main__': unittest.main()
