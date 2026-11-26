from contextlib import closing
import hashlib
import tempfile
import threading
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from client_preprep.preprep import scan, check, report, requester
from test_support import create_app


class PreprepTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.photos = self.root / 'photos'
        self.photos.mkdir()
        self.database = self.root / 'client.sqlite3'
        self.app = create_app(self.root, self.photos, self.root / 'server-db')
        self.client = self.app.test_client()
        self.library = self.app.extensions['photo_library']

    def tearDown(self):
        self.temp.cleanup()

    def send(self, files):
        response = self.client.post('/api/client-preprep/check', json={'files': files},
                                    headers={'X-Photo-Browser': '1'})
        self.assertEqual(response.status_code, 200, response.json)
        return response.json

    def test_scan_compare_duplicates_and_rebuild(self):
        for name, data in [('renamed.jpg', b'existing'), ('new.png', b'new'), ('copy.JPG', b'new')]:
            (self.photos / name).write_bytes(data)
        (self.photos / 'ignored.txt').write_text('ignored')
        (self.photos / '._ignored.jpg').write_bytes(b'ignored')
        (self.photos / 'link.jpg').symlink_to(self.photos / 'new.png')
        self.assertEqual(scan([self.photos, self.photos], self.database), 0)
        items = [{'sha256': hashlib.sha256(b'existing').hexdigest(), 'size_bytes': 8,
                  'lifecycle': {'status': 'active'}},
                 {'sha256': hashlib.sha256(b'new').hexdigest(), 'size_bytes': 3,
                  'lifecycle': {'status': 'trashed'}}]
        with patch.object(self.library, 'items', return_value=items):
            check(self.database, 'test-server', self.send)
        result = report(self.database)
        self.assertEqual(result['summary'], {'not_in_server_db': 2, 'exists': 1})
        self.assertEqual(sum(f['upload_candidate'] for f in result['files']), 1)
        (self.photos / 'new.png').unlink()
        scan([self.photos], self.database)
        self.assertEqual(report(self.database)['summary'], {'unchecked': 2})

    def test_stale_and_failed_comparison_are_not_candidates(self):
        path = self.photos / 'new.jpg'
        path.write_bytes(b'new')
        scan([self.photos], self.database)
        check(self.database, 'server', self.send)
        self.assertTrue(report(self.database)['files'][0]['upload_candidate'])
        with self.assertRaises(OSError):
            check(self.database, 'other-server', lambda _: (_ for _ in ()).throw(OSError('offline')))
        self.assertEqual(report(self.database)['summary'], {'unchecked': 1})
        self.assertNotIn('checked_at', report(self.database)['metadata'])
        path.write_bytes(b'changed')
        check(self.database, 'server', self.send)
        self.assertEqual(report(self.database)['summary'], {'stale': 1})

    def test_hash_error_and_failed_scan_preserve_database(self):
        (self.photos / 'a.jpg').write_bytes(b'a')
        with patch('client_preprep.preprep.signature', side_effect=PermissionError('unreadable')):
            self.assertEqual(scan([self.photos], self.database), 1)
        self.assertEqual(report(self.database)['summary'], {'error': 1})
        with self.assertRaises(FileNotFoundError):
            scan([self.root / 'missing'], self.database)
        self.assertEqual(report(self.database)['summary'], {'error': 1})

    def test_malformed_response_rolls_back_results(self):
        (self.photos / 'a.jpg').write_bytes(b'a')
        scan([self.photos], self.database)
        with self.assertRaises(ValueError):
            check(self.database, 'server', lambda _: {'results': []})
        self.assertEqual(report(self.database)['summary'], {'unchecked': 1})

    def test_real_http_transport_and_batch_failure(self):
        from werkzeug.serving import make_server
        (self.photos / 'a.jpg').write_bytes(b'a')
        scan([self.photos], self.database)
        server = make_server('127.0.0.1', 0, self.app)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            url = f'http://127.0.0.1:{server.server_port}'
            with patch.dict('os.environ', {'PHOTO_BROWSER_PASSWORD': 'http-test-password'}):
                check(self.database, url, requester(url, 'http-test-password', allow_http=True))
            self.assertEqual(report(self.database)['summary'], {'not_in_server_db': 1})
        finally:
            server.shutdown()
            worker.join()
            server.server_close()
        # Separate hashes force two requests; second failure must roll back the first.
        with closing(sqlite3.connect(self.database)) as db, db:
            for i in range(500):
                path = self.photos / f'{i}.jpg'
                path.write_bytes(b'a')
                db.execute('INSERT INTO files VALUES (?,?,?,?,?,?,?)',
                    (str(path), 1, path.stat().st_mtime_ns, f'{i:064x}', 'unchecked', None, None))
        calls = []
        def send(files):
            calls.append(len(files))
            if len(calls) == 2:
                raise OSError('connection lost')
            return self.send(files)
        with self.assertRaises(OSError):
            check(self.database, 'server', send)
        self.assertEqual(calls, [500, 1])
        self.assertEqual(report(self.database)['summary'], {'unchecked': 501})

    def test_validation_auth_and_csrf(self):
        endpoint = '/api/client-preprep/check'
        for data in [[], {}, {'files': []}, {'files': [{}]}, {'files': [{}] * 501},
                     {'files': [{'sha256': 'a' * 64, 'size_bytes': True}]}]:
            self.assertEqual(self.client.post(endpoint, json=data,
                             headers={'X-Photo-Browser': '1'}).status_code, 400)
        data = {'files': [{'sha256': 'a' * 64, 'size_bytes': 1}]}
        self.assertEqual(self.client.post(endpoint, json=data).status_code, 403)
        with patch.dict('os.environ', {'PHOTO_BROWSER_PASSWORD': 'secret-test'}):
            self.assertEqual(self.app.test_client().post(endpoint, json=data,
                             headers={'X-Photo-Browser': '1'}).status_code, 401)
        with self.assertRaises(ValueError):
            requester('http://example.com', 'password')


if __name__ == '__main__':
    unittest.main()
