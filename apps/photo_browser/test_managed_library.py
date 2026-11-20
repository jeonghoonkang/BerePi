import copy
import unittest
import zipfile

import test_downloads


class ManagedLibraryTests(unittest.TestCase):
    tearDown = test_downloads.DownloadTests.tearDown

    def setUp(self):
        test_downloads.DownloadTests.setUp(self)
        self.library.merge(ids=[self.ids[0]])
        self.managed = self.library.item(self.ids[0])
        self.unmerged = self.library.item(self.ids[1])

    def test_managed_listing_filters_before_pagination_search_and_dates(self):
        self.assertEqual(self.client.get('/api/library').json['total'], 2)
        result = self.client.get('/api/library?managed_only=1&limit=1').json
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['items'][0]['media_id'], self.ids[0])
        date = self.managed['capture']['date_key']
        result = self.client.get('/api/library', query_string={'managed_only': '1', 'date': date, 'category': 'family'}).json
        self.assertEqual(result['total'], 1)
        self.assertEqual(self.client.get('/api/library?managed_only=1&q=not-present').json['total'], 0)
        self.assertEqual(self.client.get('/api/library?managed_only=1&offset=1').json['items'], [])

    def test_only_current_available_managed_locations_are_accepted(self):
        valid = self.managed['locations'][-1]
        for path, status in ((self.source / 'other.jpg', 'available'),
                             (self.root / 'managed' / '.trash' / 'old.jpg', 'available'),
                             (self.root / 'managed' / 'old.jpg', 'stale')):
            with self.subTest(path=path, status=status):
                item = copy.deepcopy(self.unmerged)
                item['locations'].append({**valid, 'path': str(path), 'status': status})
                self.assertIsNone(self.library.managed_location(item))
        self.assertIsNone(self.library.managed_location(self.managed, self.root / 'new-managed'))

    def test_file_and_download_never_fall_back_to_an_original(self):
        from pathlib import Path
        url = f'/api/library/{self.ids[1]}/file'
        self.assertEqual(self.client.get(url + '?managed_only=1').status_code, 404)
        default = self.client.get(url)
        self.assertEqual(default.status_code, 200)
        default.close()
        path = Path(self.managed['locations'][-1]['path'])
        content = path.read_bytes()
        Path(self.managed['locations'][0]['path']).write_bytes(b'changed original')
        managed = self.client.get(f'/api/library/{self.ids[0]}/file?managed_only=1&download=1')
        self.assertEqual(managed.status_code, 200)
        self.assertEqual(managed.data, content)
        managed.close()
        path.unlink()
        missing = self.client.get(f'/api/library/{self.ids[0]}/file?managed_only=1')
        self.assertEqual(missing.status_code, 404)

    def test_managed_zip_excludes_unmerged_and_survives_offline_originals(self):
        from pathlib import Path
        with self.assertRaises(ValueError):
            self.store.selected_items(self.ids, managed_only=True)
        response = self.client.post('/api/downloads', json={'ids': self.ids, 'managed_only': True}, headers=self.headers)
        self.assertEqual(response.status_code, 400)
        Path(self.managed['locations'][0]['path']).unlink()
        expected = Path(self.managed['locations'][-1]['path']).read_bytes()
        result = self.store.prepare([self.ids[0]], managed_only=True)
        path, _ = self.store.get(result['download_id'])
        with zipfile.ZipFile(path) as archive:
            self.assertEqual(archive.read(archive.namelist()[0]), expected)

    def test_archived_db_entries_do_not_appear_and_tab_exists(self):
        items = self.library.items()
        next(item for item in items if item['media_id'] == self.ids[0])['lifecycle'] = {'status': 'duplicate_archived'}
        self.library.commit(items)
        self.assertEqual(self.client.get('/api/library?managed_only=1').json['total'], 0)
        html = self.client.get('/').get_data(as_text=True)
        self.assertIn('data-tab="managed-panel"', html)
        self.assertEqual(html.count('id="library-content"'), 1)


if __name__ == '__main__':
    unittest.main()
