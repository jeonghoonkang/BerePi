import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from library import atomic_json, capture_location_tags
from place_lookup import PlaceLookup


class PlaceLanguageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name)
        self.endpoint = 'http://127.0.0.1:8080/reverse'

    def test_korea_uses_korean_names_and_separate_language_caches(self):
        languages = []
        def response(request, **kwargs):
            language = parse_qs(urlsplit(request.full_url).query)['accept-language'][0]
            languages.append(language)
            address = {'country_code': 'kr', 'country': 'South Korea', 'city': 'Seoul', 'suburb': 'Jamsil-dong'}
            if language == 'ko':
                address.update(country='대한민국', city='서울특별시', suburb='잠실동')
            return io.BytesIO(json.dumps({'address': address}).encode())
        with patch('place_lookup.urlopen', side_effect=response):
            place = PlaceLookup(self.db, self.endpoint).lookup((37.511, 127.094))
            self.assertEqual(place['country_code'], 'KR')
            self.assertEqual(place['language'], 'ko')
            self.assertIn('잠실동', place['names'])
            self.assertNotIn('Jamsil-dong', place['names'])
            cached = PlaceLookup(self.db, self.endpoint).lookup((37.511, 127.094))
            self.assertEqual(cached, place)
        self.assertEqual(languages, ['en', 'ko'])

    def test_foreign_names_are_requested_in_english_and_country_code_saved(self):
        address = {'country_code': 'us', 'country': 'United States', 'city': 'New York', 'borough': 'Manhattan'}
        with patch('place_lookup.urlopen', return_value=io.BytesIO(json.dumps({'address': address}).encode())) as request:
            place = PlaceLookup(self.db, self.endpoint).lookup((40.7, -74))
        self.assertEqual(place['country_code'], 'US')
        self.assertEqual(place['language'], 'en')
        self.assertIn('United States', place['names'])
        self.assertNotIn('미국', place['names'])
        self.assertEqual(parse_qs(urlsplit(request.call_args.args[0].full_url).query)['accept-language'], ['en'])
        request.assert_called_once()

    def test_legacy_names_and_cache_are_refreshed_on_enrichment(self):
        lat, lon = 40.7, -74
        old_key = hashlib.sha256(f'v1:{self.endpoint}:{lat:.6f}:{lon:.6f}'.encode()).hexdigest()
        old = {'provider': 'nominatim', 'names': ['미국', '뉴욕'], 'address': {'city': '뉴욕'}}
        atomic_json(self.db / 'location-cache' / old_key[:2] / (old_key + '.json'), {'place': old})
        capture = {'location': {'latitude': lat, 'longitude': lon}, 'place': old}
        with patch('place_lookup.urlopen', return_value=io.BytesIO(json.dumps({'address': {
                'country_code': 'us', 'country': 'United States', 'city': 'New York'}}).encode())) as request:
            lookup = PlaceLookup(self.db, self.endpoint)
            self.assertTrue(lookup.enrich(capture))
            self.assertFalse(lookup.enrich(capture))
        request.assert_called_once()
        self.assertEqual(capture['place']['country_code'], 'US')
        self.assertNotIn('뉴욕', capture_location_tags(capture))
        self.assertIn('New York', capture_location_tags(capture))

    def test_failed_korean_query_preserves_old_data_without_english_substitution(self):
        old = {'names': ['서울'], 'address': {'city': '서울'}}
        capture = {'location': {'latitude': 37.5, 'longitude': 127}, 'place': old}
        english = io.BytesIO(json.dumps({'address': {'country_code': 'kr', 'city': 'Seoul'}}).encode())
        with patch('place_lookup.urlopen', side_effect=[english, TimeoutError]) as request:
            lookup = PlaceLookup(self.db, self.endpoint)
            self.assertFalse(lookup.enrich(capture))
            self.assertEqual(capture['place'], old)
            self.assertFalse(lookup.enrich(capture))
            self.assertEqual(request.call_count, 2)
            self.assertIsNotNone(lookup.warning)


if __name__ == '__main__':
    unittest.main()
