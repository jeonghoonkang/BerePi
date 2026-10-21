import io
import os
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from app import create_app
from downloads import download_name


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'source'
        (self.source / 'nested').mkdir(parents=True)
        for name, color in [('가족.jpg', 'red'), ('nested/가족.jpg', 'blue')]:
            Image.new('RGB', (8, 8), color).save(self.source / name)
        self.app = create_app(self.root, self.source, self.root / 'db')
        self.client = self.app.test_client()
        self.library = self.app.extensions['photo_library']
        self.library.save_config({'managed_root': str(self.root / 'managed'), 'scan_min_free_mb': 32,
                                  'sources': [{'source_id': 'photos', 'root': str(self.source), 'protocol': 'file'}]})
        self.library.scan('photos')
        self.items = self.library.items()
        self.ids = [i['media_id'] for i in self.items]
        self.store = self.app.extensions['photo_downloads']
        self.headers = {'X-Photo-Browser': '1'}

    def tearDown(self):
        self.temp.cleanup()

    def test_single_download_keeps_original_name_and_bytes(self):
        item = self.items[0]
        response = self.client.get(f"/api/library/{item['media_id']}/file?download=1")
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response.headers['Content-Disposition'])
        self.assertIn('filename*=', response.headers['Content-Disposition'])
        self.assertEqual(response.data, Path(item['locations'][0]['path']).read_bytes())
        response.close()

    def test_zip_keeps_all_bytes_and_disambiguates_duplicate_names(self):
        progress = []
        metadata = self.store.prepare(self.ids, progress.append)
        path, saved = self.store.get(metadata['download_id'])
        self.assertEqual(saved['file_count'], 2)
        with zipfile.ZipFile(path) as archive:
            self.assertEqual(set(archive.namelist()), {'가족.jpg', '가족_중복.jpg'})
            for detail, item in zip(metadata['files'], self.items):
                self.assertEqual(archive.read(detail['archive_name']), Path(item['locations'][0]['path']).read_bytes())
            self.assertTrue(all(info.compress_type == zipfile.ZIP_STORED for info in archive.infolist()))
        self.assertEqual(progress[-1]['percent'], 100)
        self.assertEqual(list(self.store.directory.glob('*.part')), [])

    def test_background_api_download_and_range(self):
        started = self.client.post('/api/downloads', json={'ids': self.ids}, headers=self.headers)
        self.assertEqual(started.status_code, 202)
        for _ in range(300):
            status = self.client.get('/api/jobs/' + started.json['job_id']).json
            if status['status'] not in {'queued', 'running'}:
                break
            time.sleep(0.01)
        self.assertEqual(status['status'], 'completed')
        self.assertEqual(status['kind'], 'download')
        token = status['result']['download_id']
        response = self.client.get('/api/downloads/' + token)
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response.headers['Content-Disposition'])
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(len(zipfile.ZipFile(io.BytesIO(response.data)).namelist()), 2)
        response.close()
        response = self.client.get('/api/downloads/' + token, headers={'Range': 'bytes=0-9'})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(len(response.data), 10)
        response.close()

    def test_invalid_and_trashed_selection_rejected_and_authenticated(self):
        for values in [[], self.ids * 51, ['missing']]:
            self.assertEqual(self.client.post('/api/downloads', json={'ids': values}, headers=self.headers).status_code, 400)
        self.assertEqual(self.client.post('/api/downloads', json={'ids': self.ids}).status_code, 403)
        self.library.trash([self.ids[0]])
        self.assertEqual(self.client.post('/api/downloads', json={'ids': [self.ids[0]]}, headers=self.headers).status_code, 400)
        with patch.dict(os.environ, {'PHOTO_BROWSER_PASSWORD': 'secret'}):
            self.assertEqual(self.client.get('/api/downloads/' + 'a' * 32).status_code, 401)
            self.assertEqual(self.client.get(f'/api/library/{self.ids[1]}/file?download=1').status_code, 401)

    def test_missing_changed_and_low_space_leave_no_archive(self):
        path = Path(self.items[1]['locations'][0]['path'])
        original = path.read_bytes()
        path.write_bytes(b'x' * len(original))
        with self.assertRaisesRegex(ValueError, '내용이 변경'):
            self.store.prepare(self.ids)
        self.assertEqual(list(self.store.directory.glob('*')), [])
        path.unlink()
        with self.assertRaises(OSError):
            self.store.prepare(self.ids)
        self.assertEqual(list(self.store.directory.glob('*')), [])
        path.write_bytes(original)
        with patch('downloads.shutil.disk_usage', return_value=SimpleNamespace(free=0)):
            with self.assertRaisesRegex(ValueError, '공간'):
                self.store.prepare(self.ids)
        self.assertEqual(list(self.store.directory.glob('*')), [])

    def test_expiration_cleanup_and_survival_after_restart(self):
        metadata = self.store.prepare(self.ids)
        fresh = create_app(self.root, self.source, self.root / 'db').test_client()
        response = fresh.get('/api/downloads/' + metadata['download_id'])
        self.assertEqual(response.status_code, 200)
        response.close()
        with patch('downloads.time.time', return_value=metadata['expires_at'] + 1):
            self.assertIsNone(self.store.get(metadata['download_id']))
        self.assertEqual(list(self.store.directory.glob('*')), [])

    def test_archive_member_names_are_safe(self):
        for name in ['../../unsafe.jpg', 'C:\\folder\\photo.jpg', '\x00name.jpg', 'CON.jpg', '😀' * 100 + '.jpg']:
            safe = download_name(name)
            self.assertNotIn('/', safe)
            self.assertNotIn('\\', safe)
            self.assertNotIn('\x00', safe)
            self.assertLessEqual(len(safe.encode('utf-8')), 220)

    def test_remote_media_download_uses_original_protocol_adapter(self):
        from contextlib import contextmanager
        original = self.library.materialize
        items = self.library.items()
        items[0]['locations'][0]['protocol'] = 'webdav'
        self.library.commit(items)
        @contextmanager
        def remote(location, transfer=None):
            if location['protocol'] == 'webdav':
                self.assertIsNotNone(transfer)
                transfer(items[0]['size_bytes'], 0)
                yield Path(items[0]['locations'][0]['path'])
            else:
                with original(location, transfer=transfer) as path:
                    yield path
        with patch.object(self.library, 'materialize', side_effect=remote):
            self.assertEqual(self.store.prepare(self.ids)['file_count'], 2)


if __name__ == '__main__':
    unittest.main()
