import hashlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from werkzeug.exceptions import ClientDisconnected

from app import create_app


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.folder = self.root / 'photos'
        self.folder.mkdir()
        self.app = create_app(self.root, self.folder, self.root / 'db')
        self.client = self.app.test_client()
        self.headers = {'X-Photo-Browser': '1'}

    def tearDown(self):
        self.temp.cleanup()

    def upload(self, name='사진.jpg', content=b'photo bytes', **kwargs):
        query = {'directory': str(self.folder), 'name': name, **kwargs.pop('query', {})}
        return self.client.post('/api/uploads', query_string=query, data=content,
                                content_type='application/octet-stream', headers=kwargs.pop('headers', self.headers), **kwargs)

    def test_upload_and_browse_without_automatic_indexing(self):
        result = self.upload(query={'modified': '1700000000123'})
        self.assertEqual(result.status_code, 201, result.json)
        self.assertEqual((self.folder / '사진.jpg').read_bytes(), b'photo bytes')
        self.assertEqual(result.json['sha256'], hashlib.sha256(b'photo bytes').hexdigest())
        self.assertFalse(result.json['renamed'])
        self.assertAlmostEqual((self.folder / '사진.jpg').stat().st_mtime, 1700000000.123, places=2)
        self.assertEqual(self.client.get('/api/browse', query_string={'path': str(self.folder)}).json['total'], 1)
        self.assertEqual(self.app.extensions['photo_library'].items(), [])
        self.assertEqual(list(self.folder.glob('*.part')), [])

    def test_collisions_preserve_existing_files_and_directories(self):
        (self.folder / '사진.jpg').write_bytes(b'original')
        self.assertEqual(self.upload(content=b'second').json['name'], '사진_중복.jpg')
        self.assertEqual(self.upload(content=b'third').json['name'], '사진_중복_2.jpg')
        self.assertEqual((self.folder / '사진.jpg').read_bytes(), b'original')
        self.assertEqual((self.folder / '사진_중복.jpg').read_bytes(), b'second')
        self.assertEqual((self.folder / '사진_중복_2.jpg').read_bytes(), b'third')
        (self.folder / 'dir.jpg').mkdir()
        self.assertEqual(self.upload(name='dir.jpg').json['name'], 'dir_중복.jpg')

    def test_invalid_names_directories_and_empty_files(self):
        for name in ['', '../photo.jpg', 'a/b.jpg', 'a\\b.jpg', 'photo.txt', '._photo.jpg']:
            self.assertEqual(self.upload(name=name).status_code, 400, name)
        self.assertEqual(self.upload(content=b'').status_code, 400)
        for directory in ['', str(self.folder / 'missing'), str(self.root / 'db' / 'config.json')]:
            self.assertEqual(self.upload(query={'directory': directory}).status_code, 400)
        self.assertEqual(self.upload(query={'directory': str(self.root.parent)}).status_code, 400)
        for modified in ['NaN', '-1', '999999999999999999999999999999999999999999999999']:
            self.assertEqual(self.upload(query={'modified': modified}).status_code, 400)
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_auth_and_csrf(self):
        self.assertEqual(self.upload(headers={}).status_code, 403)
        self.assertEqual(self.upload(headers={**self.headers, 'Origin': 'https://other.invalid'}).status_code, 403)
        with patch.dict(os.environ, {'PHOTO_BROWSER_PASSWORD': 'secret'}):
            self.assertEqual(self.upload().status_code, 401)
            self.assertEqual(self.client.get('/api/uploads/settings').status_code, 401)
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_per_request_size_limits_leave_json_limits_unchanged(self):
        with patch.dict(os.environ, {'PHOTO_BROWSER_UPLOAD_MAX_MB': '1'}):
            app = create_app(self.root, self.folder, self.root / 'small-db')
        client = app.test_client()
        response = client.post('/api/uploads', query_string={'directory': str(self.folder), 'name': 'large.mp4'},
                               data=b'x' * (1048576 + 1), content_type='application/octet-stream', headers=self.headers)
        self.assertEqual(response.status_code, 413)
        self.assertIn('error', response.json)
        self.assertEqual(list(self.folder.iterdir()), [])
        # Default upload limit exceeds the ordinary JSON body limit.
        self.assertEqual(self.upload(name='video.mp4', content=b'x' * (2 * 1048576 + 1)).status_code, 201)
        self.assertEqual(self.client.post('/api/directory-history', data='x' * (2 * 1048576 + 1),
                                         content_type='application/json', headers=self.headers).status_code, 413)

    def test_space_checks_and_disconnect_remove_partial_files(self):
        with patch('uploads.shutil.disk_usage', return_value=SimpleNamespace(free=0)):
            self.assertEqual(self.upload().status_code, 507)
        with patch('uploads.shutil.disk_usage', side_effect=[SimpleNamespace(free=10**12), SimpleNamespace(free=10**12), SimpleNamespace(free=0)]):
            self.assertEqual(self.upload(content=b'x' * (1048576 + 1)).status_code, 507)
        self.assertEqual(list(self.folder.iterdir()), [])
        class BrokenStream(io.BytesIO):
            def readinto(self, buffer):
                raise ClientDisconnected()
        response = self.client.post('/api/uploads', query_string={'directory': str(self.folder), 'name': 'broken.jpg'},
                                    input_stream=BrokenStream(b'abc'), content_type='application/octet-stream', headers=self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_storage_failure_does_not_publish_partial_file(self):
        with patch('uploads.os.link', side_effect=PermissionError('cannot publish')):
            self.assertEqual(self.upload().status_code, 409)
        self.assertEqual(list(self.folder.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
