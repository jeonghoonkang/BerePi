import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from cli import main
from library import Library


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.db = self.root / 'db'
        self.source = self.root / 'incoming'
        self.source.mkdir()
        Image.new('RGB', (8, 8)).save(self.source / 'photo.jpg')
        self.library = Library(self.db, self.root)
        self.library.save_config({'managed_root': str(self.root / 'managed'), 'scan_min_free_mb': 32,
                                  'sources': [{'source_id': 'photos', 'root': str(self.source), 'protocol': 'file'}]})

    def call(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = main(['--db', str(self.db), '--root', str(self.root), *args])
        return code, json.loads(output.getvalue()) if output.getvalue() else errors.getvalue()

    def test_pair_history_command(self):
        code, result = self.call('pair-history')
        self.assertEqual(code, 0)
        self.assertEqual(result, self.library.pair_history())
        self.assertEqual(result['items'][0]['after']['sources'][0]['source_id'], 'photos')

    def test_config_and_scan_status(self):
        code, result = self.call('config')
        self.assertEqual(code, 0)
        self.assertEqual(result['config'], self.library.config())
        self.assertEqual(self.call('status')[1]['items'][0]['status'], 'not_scanned')
        self.library.scan('photos')
        code, result = self.call('status', '--source-id', 'photos')
        self.assertEqual(code, 0)
        self.assertTrue(result['items'][0]['scan_complete'])
        self.assertEqual(result['items'][0]['scan']['processed'], 1)
        self.assertEqual(self.call('status', '--source-id', 'unknown')[0], 1)

    def test_merge_preview_execution_and_errors(self):
        self.library.scan('photos')
        code, preview = self.call('merge', '--preview')
        target = Path(preview['operations'][0]['destination'])
        self.assertEqual(code, 0)
        self.assertFalse(target.exists())
        code, report = self.call('merge')
        self.assertEqual(code, 0)
        self.assertEqual(report['operations'][0]['status'], 'copied')
        self.assertEqual(target.read_bytes(), (self.source / 'photo.jpg').read_bytes())
        target.write_bytes(b'conflict')
        code, renamed = self.call('merge')
        self.assertEqual(code, 0)
        self.assertEqual(renamed['operations'][0]['status'], 'copied')
        self.assertEqual(Path(renamed['operations'][0]['destination']).name, 'photo_중복.jpg')
        self.assertEqual(target.read_bytes(), b'conflict')

    def test_missing_db_does_not_create_config(self):
        self.db = self.root / 'missing'
        self.assertEqual(self.call('config')[0], 1)
        self.assertFalse(self.db.exists())

    def test_concurrent_writer_rejected(self):
        with self.library.writing():
            code, error = self.call('merge')
        self.assertEqual(code, 1)
        self.assertIn('다른 작업', error)

    def test_compare_success_counts_and_same_size_corruption(self):
        self.library.scan('photos')
        report = self.library.merge()
        code, result = self.call('compare')
        self.assertEqual(code, 0)
        self.assertTrue(result['ok'])
        size = (self.source / 'photo.jpg').stat().st_size
        self.assertEqual(result['sources'][0]['file_count'], 1)
        self.assertEqual(result['sources'][0]['total_bytes'], size)
        self.assertEqual(result['managed']['file_count'], 1)
        self.assertEqual(result['managed']['total_bytes'], size)
        self.assertEqual(result['verified_item_count'], 1)
        Path(report['operations'][0]['destination']).write_bytes(b'x' * size)
        self.assertEqual(self.call('compare', '--quick')[0], 0)
        code, result = self.call('compare')
        self.assertEqual(code, 1)
        self.assertEqual(result['issues'][0]['status'], 'copy_mismatch')
        self.assertEqual(result['verified_item_count'], 0)

    def test_compare_missing_copy_new_source_and_changed_source(self):
        self.library.scan('photos')
        self.assertEqual(self.call('compare')[1]['issues'][0]['status'], 'copy_not_registered')
        report = self.library.merge()
        Path(report['operations'][0]['destination']).unlink()
        (self.source / 'new.jpg').write_bytes(b'new photo')
        (self.source / 'photo.jpg').write_bytes(b'changed')
        code, result = self.call('compare')
        self.assertEqual(code, 1)
        self.assertEqual({i['status'] for i in result['issues']},
                         {'not_scanned', 'source_changed', 'copy_missing_or_unreadable'})

    def test_compare_missing_source_and_lock(self):
        self.library.scan('photos')
        self.library.merge()
        (self.source / 'photo.jpg').unlink()
        self.assertEqual(self.call('compare')[1]['issues'][0]['status'], 'source_missing_or_unreadable')
        with self.library.writing():
            self.assertEqual(self.call('compare')[0], 1)
        self.assertEqual(self.call('compare', '--source-id', 'unknown')[0], 1)

    def test_compare_shared_copy_and_ignored_files(self):
        second = self.root / 'second'
        second.mkdir()
        (second / 'photo.jpg').write_bytes((self.source / 'photo.jpg').read_bytes())
        config = self.library.config()
        config['sources'].append({'source_id': 'second', 'root': str(second), 'protocol': 'file'})
        self.library.save_config(config)
        self.library.scan('photos')
        self.library.scan('second')
        self.library.merge()
        (self.source / 'notes.txt').write_text('ignored')
        (self.source / '._photo.jpg').write_bytes(b'ignored')
        code, result = self.call('compare')
        self.assertEqual(code, 0)
        self.assertEqual(sum(s['file_count'] for s in result['sources']), 2)
        self.assertEqual(result['managed']['compared_copy_count'], 1)
        self.assertEqual(result['verified_item_count'], 2)

    def test_compare_does_not_change_metadata_and_excludes_trash(self):
        self.library.scan('photos')
        self.library.merge()
        trash = self.root / 'managed' / '.trash'
        trash.mkdir()
        (trash / 'old.jpg').write_bytes(b'old')
        before = {p: p.read_bytes() for p in self.db.rglob('*.json')}
        code, report = self.call('compare')
        self.assertEqual(code, 0)
        self.assertEqual(report['managed']['file_count'], 1)
        self.assertEqual(before, {p: p.read_bytes() for p in self.db.rglob('*.json')})

    def test_compare_inventory_error_is_failure(self):
        self.library.scan('photos')
        self.library.merge()
        with patch('copy_check.os.walk', side_effect=PermissionError('denied')):
            code, result = self.call('compare')
        self.assertEqual(code, 1)
        self.assertIn('inventory_failed', {i['status'] for i in result['issues']})


if __name__ == '__main__':
    unittest.main()
