import os
import tempfile
import unittest
from pathlib import Path
from app import create_app


class BrowserTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        (self.root / '하위 폴더').mkdir()
        (self.root / '사진.JPG').write_bytes(b'image')
        (self.root / '하위 폴더' / 'clip.mp4').write_bytes(b'0123456789')
        (self.root / 'private.txt').write_text('not media')
        os.utime(self.root / '사진.JPG', (1700000000, 1700000000))
        self.client = create_app(self.root, self.root).test_client()

    def tearDown(self):
        self.temp.cleanup()

    def test_navigation_and_recursive_scan(self):
        result = self.client.get('/api/browse', query_string={'path': str(self.root)}).json
        self.assertIsNone(result['parent'])
        self.assertEqual(result['directories'][0]['name'], '하위 폴더')
        self.assertEqual(len(result['media']), 1)
        self.assertEqual(result['media'][0]['date'], __import__('datetime').datetime.fromtimestamp(1700000000).strftime('%Y-%m-%d'))
        result = self.client.get('/api/browse', query_string={'path': str(self.root), 'recursive': '1'}).json
        self.assertEqual(len(result['media']), 2)
        child = self.client.get('/api/browse', query_string={'path': str(self.root / '하위 폴더')}).json
        self.assertEqual(child['parent'], str(self.root))

    def test_media_range_and_access_boundary(self):
        response = self.client.get('/media', query_string={'path': str(self.root / '하위 폴더' / 'clip.mp4')}, headers={'Range': 'bytes=2-5'})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.data, b'2345')
        response.close()
        self.assertEqual(self.client.get('/media', query_string={'path': str(self.root / 'private.txt')}).status_code, 404)
        self.assertEqual(self.client.get('/api/browse', query_string={'path': '/'}).status_code, 403)
        (self.root / 'escape.jpg').symlink_to('/etc/passwd')
        self.assertEqual(self.client.get('/media', query_string={'path': str(self.root / 'escape.jpg')}).status_code, 403)

    def test_page_and_missing_folder(self):
        self.assertEqual(self.client.get('/').status_code, 200)
        response = self.client.get('/static/app.js')
        self.assertEqual(response.status_code, 200)
        response.close()
        self.assertEqual(self.client.get('/api/browse', query_string={'path': str(self.root / 'missing')}).status_code, 404)


if __name__ == '__main__':
    unittest.main()
