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
        self.client = create_app(self.root, self.root, self.root / 'db').test_client()

    def tearDown(self):
        self.temp.cleanup()

    def test_navigation_and_recursive_scan(self):
        result = self.client.get('/api/browse', query_string={'path': str(self.root)}).json
        self.assertIsNone(result['parent'])
        self.assertIn('하위 폴더', [directory['name'] for directory in result['directories']])
        self.assertEqual(len(result['media']), 1)
        self.assertEqual(result['media'][0]['date'], __import__('datetime').datetime.fromtimestamp(1700000000).strftime('%Y-%m-%d'))
        result = self.client.get('/api/browse', query_string={'path': str(self.root), 'recursive': '1'}).json
        self.assertEqual(len(result['media']), 2)
        child = self.client.get('/api/browse', query_string={'path': str(self.root / '하위 폴더')}).json
        self.assertEqual(child['parent'], str(self.root))

    def test_all_formats_are_browsable_and_served(self):
        formats = {'jpg': False, 'jpeg': False, 'png': False, 'gif': False,
                   'webp': False, 'mov': True, 'avi': True, 'mp4': True}
        folder = self.root / 'formats'
        folder.mkdir()
        for extension in formats:
            (folder / f'file.{extension.upper()}').write_bytes(b'0123456789')
        result = self.client.get('/api/browse', query_string={'path': str(folder)}).json
        self.assertEqual(len(result['media']), len(formats))
        for item in result['media']:
            with self.subTest(name=item['name']):
                self.assertEqual(item['video'], formats[Path(item['name']).suffix[1:].lower()])
                with self.client.get('/media', query_string={'path': item['path']}, headers={'Range': 'bytes=2-5'}) as response:
                    self.assertEqual(response.status_code, 206)
                    self.assertEqual(response.data, b'2345')

    def test_scan_limit(self):
        for index in range(110):
            (self.root / '하위 폴더' / f'{index:03}.jpg').write_bytes(b'image')
        client = create_app(self.root, self.root, self.root / 'db', limit=100).test_client()
        result = client.get('/api/browse', query_string={'recursive': '1'}).json
        self.assertEqual(len(result['media']), 100)
        self.assertEqual(result['limit'], 100)
        self.assertTrue(result['truncated'])
        result = client.get('/api/browse').json
        self.assertEqual(len(result['media']), 1)
        self.assertFalse(result['truncated'])
        for invalid in (0, -1, 'abc'):
            with self.assertRaises(__import__('argparse').ArgumentTypeError):
                create_app(self.root, self.root, self.root / 'db', limit=invalid)

    def test_browse_batches_and_total_size(self):
        folder = self.root / 'batches'
        folder.mkdir()
        for index in range(7):
            (folder / f'{index}.jpg').write_bytes(b'x' * (index + 1))
        (folder / 'ignored.txt').write_bytes(b'ignored')
        client = create_app(self.root, self.root, self.root / 'db', limit=3).test_client()
        paths = []
        for offset, count, truncated in ((0, 3, True), (3, 3, True), (6, 1, False), (7, 0, False)):
            page = client.get('/api/browse', query_string={'path': str(folder), 'offset': offset}).json
            self.assertEqual(page['total'], 7)
            self.assertEqual(page['total_bytes'], 28)
            self.assertEqual(len(page['media']), count)
            self.assertEqual(page['truncated'], truncated)
            self.assertEqual(page['next_offset'], offset + count)
            paths.extend(item['path'] for item in page['media'])
        self.assertEqual(len(set(paths)), 7)
        for offset in ('-1', 'abc', '1.5'):
            self.assertEqual(client.get('/api/browse', query_string={'offset': offset}).status_code, 400)
        exact = client.get('/api/browse', query_string={'path': str(folder), 'offset': 4}).json
        self.assertFalse(exact['truncated'])
        empty = self.root / 'empty'
        empty.mkdir()
        page = client.get('/api/browse', query_string={'path': str(empty)}).json
        self.assertEqual((page['total'], page['total_bytes'], page['media']), (0, 0, []))

    def test_media_range_and_access_boundary(self):
        response = self.client.get('/media', query_string={'path': str(self.root / '하위 폴더' / 'clip.mp4')}, headers={'Range': 'bytes=2-5'})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.data, b'2345')
        response.close()
        self.assertEqual(self.client.get('/media', query_string={'path': str(self.root / 'private.txt')}).status_code, 404)
        self.assertEqual(self.client.get('/api/browse', query_string={'path': '/'}).status_code, 403)
        try:
            (self.root / 'escape.jpg').symlink_to('/etc/passwd')
        except OSError:
            return  # Windows accounts without symlink privileges.
        self.assertEqual(self.client.get('/media', query_string={'path': str(self.root / 'escape.jpg')}).status_code, 403)

    def test_page_and_missing_folder(self):
        self.assertEqual(self.client.get('/').status_code, 200)
        response = self.client.get('/static/app.js')
        self.assertEqual(response.status_code, 200)
        response.close()
        self.assertEqual(self.client.get('/api/browse', query_string={'path': str(self.root / 'missing')}).status_code, 404)


if __name__ == '__main__':
    unittest.main()
