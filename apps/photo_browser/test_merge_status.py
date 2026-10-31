import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from cli import main
from library import Library, atomic_json
from merge_status import merge_status


class MergeStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.db = self.root / 'db'
        self.library = Library(self.db, self.root)

    def call(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = main(['--db', str(self.db), 'merge-status', *args])
        return code, output.getvalue(), errors.getvalue()

    def record(self, directory, name, value, timestamp):
        path = self.db / directory / (name + '.json')
        atomic_json(path, value)
        os.utime(path, (timestamp, timestamp))
        return path

    def test_no_records_missing_db_and_read_only_during_writer_lock(self):
        original = (self.db / 'config.json').read_bytes()
        with self.library.writing():
            code, output, _ = self.call()
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)['items'], [])
        self.assertEqual((self.db / 'config.json').read_bytes(), original)
        self.assertFalse((self.db / 'merge-progress').exists())
        self.db = self.root / 'missing'
        self.assertEqual(self.call()[0], 1)
        self.assertFalse(self.db.exists())

    def test_legacy_web_progress_and_specific_session(self):
        self.record('merges', 'old', {'merge_id': 'old', 'status': 'completed',
                    'processed': 1, 'total': 1, 'percent': 100}, 100)
        self.record('jobs', 'web', {'kind': 'merge', 'job_id': 'web', 'status': 'running',
                    'progress': {'merge_id': 'new', 'processed': 3, 'total': 10,
                                 'percent': 30, 'current_file': '/photos/현재.jpg'}}, 200)
        self.record('jobs', 'scan', {'kind': 'scan', 'status': 'running'}, 300)
        latest = merge_status(self.db)['items'][0]
        self.assertEqual(latest['merge_id'], 'new')
        self.assertEqual(latest['percent'], 30)
        self.assertEqual(latest['current_file'], '/photos/현재.jpg')
        self.assertEqual(merge_status(self.db, 'old')['items'][0]['status'], 'completed')
        self.assertEqual(self.call('--merge-id', 'missing')[0], 1)
        self.assertEqual(self.call('--merge-id', '../invalid')[0], 1)
        self.record('merge-progress', 'broken', ['bad record'], 400)
        self.assertEqual(len(merge_status(self.db)['errors']), 1)

    def test_actual_merge_reports_in_flight_file_and_completion(self):
        source = self.root / 'source'
        source.mkdir()
        Image.new('RGB', (8, 8)).save(source / 'photo.jpg')
        config = self.library.config()
        config['sources'] = [{'source_id': 'photos', 'root': str(source)}]
        self.library.save_config(config)
        self.library.scan('photos')
        original_copy = shutil.copy2
        seen = []
        def copying(first, second):
            code, output, _ = self.call()
            self.assertEqual(code, 0)
            state = json.loads(output)['items'][0]
            seen.append(state)
            self.assertEqual(state['status'], 'running')
            self.assertEqual(state['current_action'], 'copying')
            self.assertTrue(state['current_file'].endswith('photo.jpg'))
            return original_copy(first, second)
        with patch('library.shutil.copy2', side_effect=copying):
            result = self.library.merge()
        self.assertTrue(seen)
        latest = merge_status(self.db, result['merge_id'])['items'][0]
        self.assertEqual((latest['status'], latest['processed'], latest['total'], latest['percent']),
                         ('completed', 1, 1, 100))
        self.assertEqual(latest['current_file'], result['operations'][0]['destination'])

    def test_failure_is_saved_and_preview_is_not_a_merge(self):
        self.library.merge(preview=True)
        self.assertEqual(merge_status(self.db)['items'], [])
        with patch.object(self.library, '_merge', side_effect=ValueError('merge failed')):
            with self.assertRaisesRegex(ValueError, 'merge failed'):
                self.library.merge()
        latest = merge_status(self.db)['items'][0]
        self.assertEqual(latest['status'], 'failed')
        self.assertEqual(latest['error'], 'merge failed')

    def test_watch_refreshes_until_ctrl_c_without_changing_merge(self):
        def refresh(_):
            if not (self.db / 'merges' / 'watched.json').exists():
                self.record('merges', 'watched', {'merge_id': 'watched', 'status': 'completed',
                            'processed': 1, 'total': 1, 'percent': 100}, 100)
            else:
                raise KeyboardInterrupt
        with patch('cli.time.sleep', side_effect=refresh) as sleep:
            code, output, errors = self.call('--watch', '--interval', '0.5')
        self.assertEqual(code, 130)
        decoder = json.JSONDecoder()
        first, end = decoder.raw_decode(output)
        second, _ = decoder.raw_decode(output[end:].lstrip())
        self.assertEqual(first['items'], [])
        self.assertEqual(second['items'][0]['status'], 'completed')
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(sleep.call_args.args, (0.5,))
        self.assertIn('중단', errors)

    def test_invalid_watch_intervals(self):
        for value in ('0', '-1', 'nan', 'inf', 'abc'):
            with self.subTest(value=value), self.assertRaises(SystemExit) as raised:
                self.call('--interval', value)
            self.assertEqual(raised.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
