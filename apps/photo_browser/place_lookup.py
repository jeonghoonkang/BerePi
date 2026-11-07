"""Optional reverse geocoding through an operator-configured Nominatim server."""
import hashlib
import json
import re
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from library import atomic_json, gps_coordinates, read_json


ADDRESS_KEYS = ('country', 'state', 'province', 'region', 'state_district', 'county', 'municipality',
                'city', 'town', 'village', 'borough', 'city_district', 'district', 'suburb',
                'quarter', 'neighbourhood', 'hamlet', 'locality')
LANGUAGE_POLICY = 'en-default-ko-for-kr-v1'


def country_code(address):
    code = address.get('country_code')
    return code.upper() if isinstance(code, str) and re.fullmatch(r'[A-Za-z]{2}', code) else None


def place_from_address(address, language='en'):
    names = {key: address[key].strip() for key in ADDRESS_KEYS
             if isinstance(address.get(key), str) and address[key].strip()}
    if not names:
        return None
    code = country_code(address)
    tags = list(dict.fromkeys((['한국'] if code == 'KR' else []) + list(names.values())))
    return {'provider': 'nominatim', 'address': names, 'names': tags, 'country_code': code,
            'language': language, 'language_policy': LANGUAGE_POLICY}


def current_policy(place):
    return isinstance(place, dict) and place.get('language_policy') == LANGUAGE_POLICY


class PlaceLookup:
    def __init__(self, db, endpoint):
        self.directory = db / 'location-cache'
        self.endpoint = endpoint.strip()
        self.warning = None
        if self.endpoint:
            try:
                url = urlsplit(self.endpoint)
                if (url.scheme not in {'http', 'https'} or not url.hostname or url.username or url.password
                        or url.query or url.fragment or url.hostname.lower().rstrip('.') == 'nominatim.openstreetmap.org'):
                    raise ValueError
            except ValueError:
                self.endpoint = ''
                self.warning = '위치 이름 조회 주소가 올바르지 않습니다. 자체 운영하는 Nominatim /reverse 주소를 지정하세요.'

    def enrich(self, capture, previous=None):
        coordinates = gps_coordinates(capture)
        if coordinates is None or current_policy(capture.get('place')):
            return False
        if previous and gps_coordinates(previous) == coordinates and current_policy(previous.get('place')):
            capture['place'] = previous['place']
            return False
        place = self.lookup(coordinates)
        if place:
            capture['place'] = place
            return True
        return False

    def lookup(self, coordinates):
        if not self.endpoint or coordinates is None:
            return None
        try:
            address = self._address(coordinates, 'en')
            language = 'en'
            if country_code(address) == 'KR':
                address = self._address(coordinates, 'ko')
                if country_code(address) != 'KR':
                    raise ValueError('국가 판별 결과가 일치하지 않습니다.')
                language = 'ko'
            return place_from_address(address, language)
        except (OSError, ValueError):
            self.warning = '위치 이름 조회에 실패했습니다. 나머지 스캔은 계속하며 기존 위치 정보와 GPS 좌표를 유지합니다.'
            return None

    def _address(self, coordinates, language):
        lat, lon = coordinates
        key = hashlib.sha256(f'v2:{language}:{self.endpoint}:{lat:.6f}:{lon:.6f}'.encode()).hexdigest()
        path = self.directory / key[:2] / (key + '.json')
        try:
            cached = read_json(path)
            if isinstance(cached, dict) and isinstance(cached.get('address'), dict):
                return cached['address']
        except (OSError, ValueError):
            pass
        if self.warning:
            raise ValueError('조회 서버가 응답하지 않습니다.')
        params = urlencode({'format': 'jsonv2', 'lat': lat, 'lon': lon, 'addressdetails': 1,
                            'zoom': 18, 'accept-language': language})
        try:
            request = Request(f'{self.endpoint}?{params}', headers={'User-Agent': 'BerePi-PhotoBrowser/1.0'})
            try:
                with urlopen(request, timeout=4) as response:
                    data = json.loads(response.read(128 * 1024))
            except HTTPError as exc:
                with exc:
                    if exc.code != 404:
                        raise
                    data = json.loads(exc.read(128 * 1024))
                    if not isinstance(data, dict) or data.get('error') != 'Unable to geocode':
                        raise
                data = {'address': {}}
            address = data.get('address') if isinstance(data, dict) else None
            if not isinstance(address, dict):
                raise ValueError
            atomic_json(path, {'address': address})
            return address
        except (OSError, ValueError):
            raise
