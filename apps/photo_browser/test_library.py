import json
import os
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from app import create_app
from library import metadata, read_json


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / 'photos'
        self.source.mkdir()
        self.app = create_app(self.root, self.root, self.root / 'db')
        self.client = self.app.test_client()
        self.library = self.app.extensions['photo_library']
        self.config = {'managed_root': str(self.root / 'organized'), 'sources': [{'source_id': 'local', 'protocol': 'file', 'root': str(self.source), 'category': 'family', 'owner_id': 'alice', 'recursive': True}]}
        self.library.save_config(self.config)
        self.headers = {'X-Photo-Browser': '1'}

    def tearDown(self):
        self.temporary.cleanup()

    def photo(self, name='photo.jpg', color='red'):
        path = self.source / name
        exif = Image.Exif()
        # Top-level DateTimeOriginal is accepted in addition to nested EXIF IFD.
        exif[36867] = '2024:03:05 12:30:00'
        Image.new('RGB', (8, 8), color).save(path, exif=exif)
        return path

    def post(self, path, data):
        return self.client.post(path, json=data, headers=self.headers)

    def test_month_chunks_and_incremental_edit_preservation(self):
        path = self.photo()
        for i in range(100):
            (self.source / f'copy{i}.jpg').write_bytes(path.read_bytes())
        report = self.library.scan('local')
        self.assertEqual(report['added'], 101)
        index = read_json(self.root / 'db/index.json')
        self.assertEqual([c['count'] for c in index['chunks']], [100, 1])
        for chunk in index['chunks']:
            self.assertEqual(Path(chunk['path']).parent.as_posix(), 'media/family/alice/2024/03')
        item = self.library.items()[0]
        self.library.edit([item['media_id']], {'events': ['제주 여행'], 'tags': ['바다'], 'person_ids': ['bob']})
        self.assertEqual(self.library.scan('local')['updated'], 0)
        response = self.client.get('/api/library?event=제주 여행&tag=바다&person=bob&from=2024-03-05&to=2024-03-05').json
        self.assertEqual(response['total'], 1)
        self.assertEqual(response['items'][0]['media_id'], item['media_id'])
        self.assertEqual(len(self.library.duplicates()['exact'][0]['members']), 101)

    def test_merge_verified_shared_trash_restore_and_purge(self):
        first = self.photo()
        (self.source / 'nested').mkdir()
        (self.source / 'nested' / first.name).write_bytes(first.read_bytes())
        self.library.scan('local')
        ids = [i['media_id'] for i in self.library.items()]
        self.assertTrue(all(o['status'] == 'planned' for o in self.library.merge(preview=True)['operations']))
        self.assertFalse((self.root / 'organized').exists())
        result = self.library.merge()
        self.assertEqual([o['status'] for o in result['operations']], ['copied', 'reused'])
        target = Path(result['operations'][0]['destination'])
        self.assertEqual(target.parent.relative_to(self.root / 'organized').as_posix(), 'family/alice/2024/03')
        trash1 = self.library.trash([ids[0]])
        self.assertTrue(target.exists())
        trash2 = self.library.trash([ids[1]])
        self.assertFalse(target.exists())
        # Restore an earlier logical delete whose shared bytes were moved later.
        self.library.restore(trash1['trash_id'])
        self.assertTrue(target.exists())
        self.library.restore(trash2['trash_id'])
        trash = self.library.trash(ids)
        self.assertTrue(first.exists())
        self.assertEqual(self.library.scan('local')['added'], 0)
        self.assertEqual(self.client.get('/api/library').json['total'], 0)
        self.assertEqual(self.post(f"/api/trash/{trash['trash_id']}/purge", {}).status_code, 400)
        prepared = self.post(f"/api/trash/{trash['trash_id']}/prepare", {}).json
        purged = self.post(f"/api/trash/{trash['trash_id']}/purge", {'token': prepared['token'], 'phrase': prepared['phrase']})
        self.assertEqual(purged.json['status'], 'purged')
        self.assertTrue(first.exists())
        with self.assertRaises(ValueError):
            self.library.restore(trash['trash_id'])

    def test_merge_preserves_original_names_and_rejects_collision(self):
        original = self.photo('가족 사진.JPG')
        (self.source / 'nested').mkdir()
        other = self.source / 'nested' / original.name
        with Image.open(original) as image:
            exif = image.getexif()
        Image.new('RGB', (8, 8), 'blue').save(other, exif=exif)
        self.library.scan('local')
        preview = self.library.merge(preview=True)
        self.assertTrue(all(Path(op['destination']).name == original.name for op in preview['operations']))
        result = self.library.merge()
        self.assertEqual(sorted(op['status'] for op in result['operations']), ['copied', 'error'])
        target = Path(result['operations'][0]['destination'])
        self.assertIn(target.read_bytes(), (original.read_bytes(), other.read_bytes()))

    def test_duplicate_source_path_and_rename(self):
        self.photo()
        self.library.scan('local')
        before = self.library.items()[0]['media_id']
        duplicate = dict(self.config, sources=self.config['sources'] + [dict(self.config['sources'][0], source_id='other', root=str(self.source / '.'))])
        with self.assertRaisesRegex(ValueError, '기존 소스 ID: local'):
            self.library.save_config(duplicate)
        check = self.post('/api/sources/check', {'root': str(self.source / '.'), 'protocol': 'file'})
        self.assertEqual(check.json['existing']['source_id'], 'local')
        renamed = self.post('/api/sources/rename', {'old_id': 'local', 'new_id': 'family_photos'})
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(self.library.items()[0]['locations'][0]['source_id'], 'family_photos')
        self.library.scan('family_photos')
        self.assertEqual(len(self.library.items()), 1)
        self.assertEqual(self.library.items()[0]['media_id'], before)

    def test_merge_stop_and_resume_after_restart(self):
        for index in range(4):
            self.photo(f'photo{index}.jpg')
        self.library.scan('local')
        stop = [False]
        def progress(state):
            if state['processed'] >= 1:
                stop[0] = True
        result = self.library.merge(progress=progress, stopped=lambda: stop[0])
        self.assertEqual(result['status'], 'stopped')
        self.assertEqual(result['processed'], 1)
        self.assertEqual(len(list((self.root / 'organized').rglob('*.jpg'))), 1)
        from library import Library
        restarted = Library(self.root / 'db', self.root)
        result = restarted.merge(resume=result['merge_id'])
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['processed'], 4)
        self.assertTrue(all(op['status'] == 'copied' for op in result['operations']))
        self.assertEqual(len(list((self.root / 'organized').rglob('*.jpg'))), 4)

    def test_changed_original_no_overwrite_and_integrity(self):
        source = self.photo()
        self.library.scan('local')
        item = self.library.items()[0]
        source.write_bytes(b'changed source')
        result = self.library.merge()
        self.assertEqual(result['operations'][0]['status'], 'error')
        self.library.verify([item['media_id']], True)
        self.assertEqual(self.library.items()[0]['verification']['results'][0]['status'], 'changed')
        source.unlink()
        self.library.scan('local')
        self.assertEqual(self.library.items()[0]['locations'][0]['status'], 'missing')

    def test_restore_conflict_keeps_trash(self):
        self.photo()
        self.library.scan('local')
        self.library.merge()
        entry = self.library.trash([self.library.items()[0]['media_id']])
        Path(entry['moves'][0]['original']).write_bytes(b'conflict')
        with self.assertRaises(ValueError):
            self.library.restore(entry['trash_id'])
        self.assertTrue(Path(entry['moves'][0]['trash']).exists())

    def test_purging_shared_trash_preserves_other_undo(self):
        source = self.photo()
        (self.source / 'nested').mkdir()
        (self.source / 'nested' / source.name).write_bytes(source.read_bytes())
        self.library.scan('local')
        self.library.merge()
        ids = [i['media_id'] for i in self.library.items()]
        first = self.library.trash([ids[0]])
        second = self.library.trash([ids[1]])
        self.library.purge(second['trash_id'])
        self.assertTrue(Path(second['moves'][0]['trash']).exists())
        self.library.restore(first['trash_id'])
        self.assertTrue(Path(second['moves'][0]['original']).exists())

    def test_last_shared_trash_purge_removes_retained_bytes(self):
        source = self.photo()
        (self.source / 'nested').mkdir()
        (self.source / 'nested' / source.name).write_bytes(source.read_bytes())
        self.library.scan('local')
        self.library.merge()
        ids = [i['media_id'] for i in self.library.items()]
        first = self.library.trash([ids[0]])
        second = self.library.trash([ids[1]])
        self.library.purge(second['trash_id'])
        self.library.purge(first['trash_id'])
        self.assertFalse(Path(second['moves'][0]['trash']).exists())

    def test_boundaries_write_guard_auth_and_config_validation(self):
        self.assertEqual(self.client.put('/api/config', json=self.config).status_code, 403)
        self.assertEqual(self.client.put('/api/config', json=self.config, headers={**self.headers, 'Origin': 'https://evil.example'}).status_code, 403)
        invalid = {**self.config, 'managed_root': str(self.root.parent / 'outside')}
        self.assertEqual(self.client.put('/api/config', json=invalid, headers=self.headers).status_code, 400)
        for category in ['../escape', 'CON', 'family/name']:
            with self.assertRaises(ValueError):
                self.library.save_config({**self.config, 'sources': [{**self.config['sources'][0], 'category': category}]})
        with patch.dict(os.environ, {'PHOTO_BROWSER_PASSWORD': 'test-password'}):
            self.assertEqual(self.client.get('/api/config').status_code, 401)
            self.assertEqual(self.client.get('/api/config', auth=('user', 'test-password')).status_code, 200)
        for url in ['http://evil.example/a.jpg', 'http://localhost/other/a.jpg', 'http://localhost/photos/%2e%2e/a.jpg']:
            with self.assertRaises(ValueError):
                self.library.remote_open({'root': 'http://localhost/photos/'}, url)

    def test_job_api_and_original_media(self):
        self.photo()
        response = self.post('/api/scan', {'source_id': 'local'})
        self.assertEqual(response.status_code, 202)
        for _ in range(100):
            result = self.client.get('/api/jobs/' + response.json['job_id']).json
            if result['status'] not in {'queued', 'running'}:
                break
            time.sleep(0.02)
        self.assertEqual(result['status'], 'completed')
        item = self.client.get('/api/library').json['items'][0]
        response = self.client.get(f"/api/library/{item['media_id']}/file")
        self.assertEqual(response.status_code, 200)
        response.close()
        self.assertEqual(self.client.get(f"/api/library/{item['media_id']}").json['name'], 'photo.jpg')

    def test_interrupted_trash_can_restore(self):
        self.photo()
        self.library.scan('local')
        self.library.merge()
        with patch.object(self.library, 'commit', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                self.library.trash([self.library.items()[0]['media_id']])
        entry = self.library.trash_entries()[0]
        self.assertEqual(entry['status'], 'recovery_required')
        self.library.restore(entry['trash_id'])
        self.assertTrue(Path(entry['moves'][0]['original']).exists())

    def test_http_and_webdav_sources(self):
        image = self.photo().read_bytes()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.path == '/photos/manifest.json':
                    payload = json.dumps({'files': [{'path': 'remote.jpg', 'modified': '2023-02-10T12:00:00Z'}]}).encode()
                else:
                    payload = image
                self.send_response(200)
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_PROPFIND(self):
                payload = b'<d:multistatus xmlns:d="DAV:"><d:response><d:href>/photos/remote.jpg</d:href><d:propstat><d:prop><d:getcontentlength>100</d:getcontentlength></d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response></d:multistatus>'
                self.send_response(207)
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for protocol in ['http', 'webdav']:
                source = {'source_id': protocol, 'protocol': protocol, 'root': f'http://127.0.0.1:{server.server_port}/photos/', 'category': 'family', 'owner_id': 'alice'}
                self.config['sources'].append(source)
                self.library.save_config(self.config)
                report = self.library.scan(protocol)
                self.assertEqual(report['errors'], [])
                self.assertEqual(report['added'], 1)
            result = self.library.merge()
            self.assertTrue(all(op['status'] != 'error' for op in result['operations']))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_video_capture_metadata(self):
        video = self.source / 'clip.mp4'
        video.write_bytes(b'video')
        payload = {'format': {'tags': {'creation_time': '2024-04-05T06:07:08Z', 'location': '+37.5665+126.9780/'}, 'duration': '12.5'}, 'streams': [{'codec_type': 'video', 'width': 1920, 'height': 1080}]}
        with patch('library.subprocess.run', return_value=type('Probe', (), {'stdout': json.dumps(payload)})()):
            info = metadata(video)
        self.assertEqual(info['date_key'], '2024-04-05')
        self.assertEqual(info['duration_seconds'], 12.5)
        self.assertEqual(info['location']['latitude'], 37.5665)
        self.assertEqual(info['width'], 1920)

    def test_restore_rejects_tampered_path_and_purge_requires_fresh_token(self):
        self.photo()
        self.library.scan('local')
        self.library.merge()
        entry = self.library.trash([self.library.items()[0]['media_id']])
        prepared = self.post(f"/api/trash/{entry['trash_id']}/prepare", {}).json
        wrong = self.post(f"/api/trash/{entry['trash_id']}/purge", {'token': prepared['token'], 'phrase': 'wrong'})
        self.assertEqual(wrong.status_code, 400)
        retry = self.post(f"/api/trash/{entry['trash_id']}/purge", {'token': prepared['token'], 'phrase': prepared['phrase']})
        self.assertEqual(retry.status_code, 400)
        path = self.root / 'db/trash' / (entry['trash_id'] + '.json')
        entry['moves'][0]['original'] = str(self.source / 'injected.jpg')
        path.write_text(json.dumps(entry), encoding='utf-8')
        with self.assertRaises(ValueError):
            self.library.restore(entry['trash_id'])


if __name__ == '__main__':
    unittest.main()
