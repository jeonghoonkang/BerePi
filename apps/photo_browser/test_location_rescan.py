import copy
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app import create_app
from library import Library
from location_rescan import scan_missing_places
from place_lookup import LANGUAGE_POLICY, place_from_address


class MissingPlaceScanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'photos'
        self.source.mkdir()
        for i in range(3):
            Image.new('RGB', (8, 8), (i * 50, 30, 70)).save(self.source / f'{i}.jpg')
        self.library = Library(self.root / 'db', self.root)
        self.library.save_config({'managed_root': str(self.root / 'managed'), 'scan_min_free_mb': 32,
                                  'sources': [{'source_id': 'a', 'root': str(self.source), 'protocol': 'file',
                                               'category': 'family', 'owner_id': 'alice'}]})
        self.library.scan('a')
        items = sorted(self.library.items(), key=lambda item: item['name'])
        for item in items:
            item['capture']['location'] = {'latitude': 37.5, 'longitude': 127.1}
            item['classification']['tags'] = ['keep-me']
        items[0]['capture']['place'] = place_from_address({'country': '대한민국', 'country_code': 'kr'}, 'ko')
        items[1]['capture']['place'] = {'language_policy': LANGUAGE_POLICY, 'names': []}
        self.library.commit(items)
        self.before = {i['media_id']: i for i in self.library.items()}
        self.env = patch.dict(os.environ, {'PHOTO_BROWSER_REVERSE_GEOCODER_URL': 'http://127.0.0.1:8080/reverse'})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_only_missing_names_are_looked_up_and_existing_data_is_preserved(self):
        files = {path: path.read_bytes() for path in self.source.glob('*.jpg')}
        place = place_from_address({'country': '대한민국', 'city': '서울', 'country_code': 'kr'}, 'ko')
        with patch('location_rescan.PlaceLookup.lookup', return_value=place) as lookup, patch('location_rescan.metadata') as metadata:
            report = scan_missing_places(self.library, lambda _: None, lambda: False)
        self.assertEqual((report['total'], report['processed'], report['updated']), (2, 2, 2))
        self.assertEqual(lookup.call_count, 2)
        metadata.assert_not_called()
        for item in self.library.items():
            old = self.before[item['media_id']]
            self.assertEqual(item['classification']['tags'], ['keep-me'])
            self.assertEqual(item['locations'], old['locations'])
            self.assertEqual(item['capture']['date_key'], old['capture']['date_key'])
            if old['name'] == '0.jpg':
                self.assertEqual(item, old)
            else:
                self.assertIn('서울', item['classification']['location_tags'])
        self.assertTrue(all(path.read_bytes() == content for path, content in files.items()))

    def test_stop_saves_updates_and_next_run_only_handles_remaining_photos(self):
        stop = threading.Event()
        def progress(state):
            if state['processed'] == 1:
                stop.set()
        place = place_from_address({'country': 'South Korea'})
        with patch('location_rescan.PlaceLookup.lookup', return_value=place):
            first = scan_missing_places(self.library, progress, stop.is_set)
            self.assertEqual((first['status'], first['updated']), ('stopped', 1))
            second = scan_missing_places(self.library, lambda _: None, lambda: False)
            self.assertEqual((second['total'], second['updated']), (1, 1))

    def test_no_gps_and_non_photos_are_not_geocoded(self):
        items = self.library.items()
        for item in items:
            item['capture']['location'] = None
        video = copy.deepcopy(items[-1])
        video.update(media_id='video-id', media_type='video')
        inactive = copy.deepcopy(items[-1])
        inactive.update(media_id='inactive-id', lifecycle={'status': 'trashed'})
        self.library.commit([*items, video, inactive])
        with patch('location_rescan.PlaceLookup.lookup') as lookup:
            report = scan_missing_places(self.library, lambda _: None, lambda: False)
        lookup.assert_not_called()
        self.assertEqual((report['total'], report['no_gps'], report['updated']), (2, 2, 0))

    def test_missing_gps_is_recovered_from_photo_without_replacing_other_metadata(self):
        items = self.library.items()
        target = next(item for item in items if item['name'] == '1.jpg')
        target['capture']['location'] = None
        self.library.commit(items)
        gps = {'latitude': 35.0, 'longitude': 129.0}
        place = place_from_address({'city': 'Busan'})
        with patch('location_rescan.metadata', return_value={'location': gps}) as read, patch('location_rescan.PlaceLookup.lookup', return_value=place):
            result = scan_missing_places(self.library, lambda _: None, lambda: False)
        self.assertEqual(read.call_count, 1)
        self.assertEqual(result['no_gps'], 0)
        updated = next(item for item in self.library.items() if item['name'] == '1.jpg')
        self.assertEqual(updated['capture']['location'], gps)
        self.assertEqual(updated['capture']['date_key'], target['capture']['date_key'])

    def test_api_requires_ready_server_and_exposes_job_progress(self):
        app = create_app(self.root, self.root, self.library.db)
        client = app.test_client()
        with patch('nominatim_docker._healthy', return_value=False):
            self.assertEqual(client.post('/api/nominatim/scan-missing', headers={'X-Photo-Browser': '1'}).status_code, 409)
        place = place_from_address({'country': 'South Korea'})
        with patch('nominatim_docker._healthy', return_value=True), patch('location_rescan.PlaceLookup.lookup', return_value=place):
            response = client.post('/api/nominatim/scan-missing', headers={'X-Photo-Browser': '1'})
            self.assertEqual(response.status_code, 202)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                job = client.get('/api/jobs/' + response.json['job_id']).json
                if job['status'] not in {'queued', 'running'}:
                    break
                time.sleep(.01)
            self.assertEqual(job['status'], 'completed', job)
            self.assertEqual(job['result']['updated'], 2)
            self.assertEqual(client.get('/api/nominatim/statistics').json['missing_place_photo_count'], 0)


if __name__ == '__main__':
    unittest.main()
