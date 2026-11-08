import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app import create_app
from library import atomic_json
from nominatim_statistics import PhotoTagStatistics


def photo(mid, tags=(), locations=(), **changes):
    return {'media_id': mid, 'media_type': 'image', 'lifecycle': {'status': 'active'},
            'classification': {'tags': list(tags), 'location_tags': list(locations)}, 'capture': {}, **changes}


class PhotoTagStatisticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name)
        self.stats = PhotoTagStatistics(SimpleNamespace(db=self.db))

    def tearDown(self):
        self.temp.cleanup()

    def publish(self, items, path='catalog/a.json'):
        atomic_json(self.db / path, {'items': items})
        atomic_json(self.db / 'index.json', {'chunks': [{'path': path}], 'updated_at': 'version'})

    def test_photo_denominator_duplicate_tags_and_missing_counts(self):
        self.publish([photo('1', ['가족', '가족', '', ' '], ['한국', '서울']),
                      photo('2', [], ['한국']), photo('3'),
                      photo('1', ['중복 ID']),
                      photo('video', ['동영상 전용'], media_type='video'),
                      photo('trash', ['휴지통 전용'], lifecycle={'status': 'trashed'})])
        result = self.stats.snapshot()
        self.assertEqual(result['total_photos'], 3)
        self.assertEqual(result['tag_count'], 3)
        location = result['groups']['location_tags']
        korea, seoul = location['items']
        self.assertEqual(korea, {'tag': '한국', 'photo_count': 2, 'percent': 66.67,
                                'missing_photo_count': 1, 'missing_percent': 33.33})
        self.assertEqual(seoul['photo_count'], 1)
        self.assertEqual(location['empty_photo_count'], 1)
        self.assertEqual(result['groups']['tags']['empty_photo_count'], 2)

    def test_empty_db_and_old_location_tags_fallback(self):
        result = self.stats.snapshot()
        self.assertEqual(result['total_photos'], 0)
        self.assertEqual(result['missing_gps_photo_count'], 0)
        self.assertEqual(result['missing_gps_percent'], 0)
        self.assertEqual(result['groups']['location_tags']['empty_percent'], 0)
        item = photo('legacy')
        del item['classification']['location_tags']
        item['capture'] = {'place': {'names': ['한국', '서울']}}
        self.publish([item])
        self.assertEqual(self.stats.snapshot()['groups']['location_tags']['tag_count'], 2)

    def test_gps_missing_count_uses_valid_coordinates_not_tag_names(self):
        valid = photo('valid')
        valid['capture']['location'] = {'latitude': 0, 'longitude': 0}
        invalid = photo('invalid', locations=['서울'])
        invalid['capture']['location'] = {'latitude': 91, 'longitude': 127}
        self.publish([valid, invalid, photo('absent'), photo('valid'),
                      photo('video', media_type='video'),
                      photo('inactive', lifecycle={'status': 'trashed'})])
        result = self.stats.snapshot()
        self.assertEqual(result['total_photos'], 3)
        self.assertEqual(result['missing_gps_photo_count'], 2)
        self.assertEqual(result['missing_gps_percent'], 66.67)

    def test_cache_changes_with_catalog_generation_and_force_refresh(self):
        self.publish([photo('1')])
        self.assertFalse(self.stats.snapshot()['cached'])
        self.assertTrue(self.stats.snapshot()['cached'])
        self.publish([photo('1'), photo('2')], 'catalog/b.json')
        self.assertEqual(self.stats.snapshot()['total_photos'], 2)
        self.assertFalse(self.stats.snapshot(refresh=True)['cached'])

    def test_invalid_catalog_is_an_error(self):
        self.publish([])
        atomic_json(self.db / 'catalog/a.json', {'invalid': True})
        with self.assertRaisesRegex(ValueError, '청크'):
            self.stats.snapshot()

    def test_api_pagination_search_and_validation(self):
        app = create_app(self.db, self.db, self.db / 'database')
        db = app.extensions['photo_library'].db
        atomic_json(db / 'catalog/photos.json', {'items': [photo('1', locations=[f'tag{i:03}' for i in range(125)])]})
        atomic_json(db / 'index.json', {'chunks': [{'path': 'catalog/photos.json'}]})
        client = app.test_client()
        response = client.get('/api/nominatim/statistics')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(response.json['total_photos'], 1)
        self.assertEqual(len(response.json['items']), 100)
        self.assertEqual(response.json['matched_tags'], 125)
        self.assertNotIn('items', response.json['groups']['location_tags'])
        page = client.get('/api/nominatim/statistics?offset=100').json
        self.assertEqual(len(page['items']), 25)
        found = client.get('/api/nominatim/statistics?q=TAG124').json
        self.assertEqual(found['items'][0]['tag'], 'tag124')
        self.assertEqual(found['items'][0]['percent'], 100)
        for query in ('offset=-1', 'offset=abc', 'kind=invalid'):
            self.assertEqual(client.get('/api/nominatim/statistics?' + query).status_code, 400)


if __name__ == '__main__':
    unittest.main()
