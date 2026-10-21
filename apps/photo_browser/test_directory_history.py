import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from app import create_app
from directory_history import DirectoryHistory


class DirectoryHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.folder = self.root / '사진 폴더'
        self.folder.mkdir()
        self.db = self.root / 'db'
        self.app = create_app(self.root, self.folder, self.db)
        self.client = self.app.test_client()
        self.history = self.app.extensions['directory_history']
        self.headers = {'X-Photo-Browser': '1'}

    def tearDown(self):
        self.temp.cleanup()

    def test_record_kst_timestamp_recursive_option_and_restart_persistence(self):
        response = self.client.post('/api/directory-history', json={'path': str(self.folder), 'recursive': True}, headers=self.headers)
        self.assertEqual(response.status_code, 201)
        record = response.json['item']
        self.assertEqual(record['path'], str(self.folder))
        self.assertTrue(record['recursive'])
        self.assertEqual(datetime.fromisoformat(record['recorded_at']).utcoffset(), timedelta(hours=9))
        saved = json.loads((self.db / 'history.txt').read_text(encoding='utf-8'))
        self.assertEqual(saved, record)
        reloaded = create_app(self.root, self.folder, self.db).test_client()
        self.assertEqual(reloaded.get('/api/directory-history').json['items'][0], record)

    def test_keep_latest_1000_records_in_order_and_allow_repeated_visits(self):
        first = self.history.add(self.folder)
        entries = [{**first, 'id': str(index)} for index in range(1000)]
        self.history.path.write_text(''.join(json.dumps(entry) + '\n' for entry in entries), encoding='utf-8')
        newest = self.history.add(self.folder, True)
        values, _ = self.history.entries()
        self.assertEqual(len(values), 1000)
        self.assertEqual(values[0], newest)
        self.assertEqual(values[-1]['id'], '1')
        self.assertEqual(len(self.history.path.read_text(encoding='utf-8').splitlines()), 1000)

    def test_concurrent_updates_do_not_lose_entries(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            entries = list(pool.map(lambda _: self.history.add(self.folder), range(24)))
        saved, invalid = self.history.entries()
        self.assertEqual({item['id'] for item in saved}, {item['id'] for item in entries})
        self.assertEqual(invalid, 0)

    def test_write_failure_preserves_previous_history(self):
        first = self.history.add(self.folder)
        with patch('directory_history.os.replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.history.add(self.folder)
        self.assertEqual(self.history.entries()[0], [first])
        self.assertEqual(list(self.db.glob('history.*.tmp')), [])

    def test_corrupt_lines_are_backed_up_before_saving_valid_records(self):
        first = self.history.add(self.folder)
        with self.history.path.open('a', encoding='utf-8') as stream:
            stream.write('{broken\n')
        self.assertEqual(self.history.entries()[1], 1)
        newest = self.history.add(self.folder)
        entries, invalid = self.history.entries()
        self.assertEqual(entries, [newest, first])
        self.assertEqual(invalid, 0)
        backup = list(self.db.glob('history.corrupt.*.txt'))
        self.assertEqual(len(backup), 1)
        self.assertIn('{broken', backup[0].read_text(encoding='utf-8'))

    def test_validation_auth_and_history_reads_do_not_create_entries(self):
        self.assertEqual(self.client.get('/api/directory-history').json['items'], [])
        self.client.get('/api/browse', query_string={'path': str(self.folder)})
        self.assertFalse(self.history.path.exists())
        for body, code in [({'path': str(self.root.parent)}, 403), ({'path': str(self.root / 'missing')}, 404), ({'path': ''}, 400), ({'path': str(self.folder), 'recursive': 'yes'}, 400)]:
            self.assertEqual(self.client.post('/api/directory-history', json=body, headers=self.headers).status_code, code)
        self.assertFalse(self.history.path.exists())
        self.assertEqual(self.client.post('/api/directory-history', json={'path': str(self.folder)}).status_code, 403)
        with patch.dict(os.environ, {'PHOTO_BROWSER_PASSWORD': 'password'}):
            self.assertEqual(self.client.get('/api/directory-history').status_code, 401)


if __name__ == '__main__':
    unittest.main()
