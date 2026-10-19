import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

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
        self.assertEqual(self.call('merge')[0], 1)
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


if __name__ == '__main__':
    unittest.main()
