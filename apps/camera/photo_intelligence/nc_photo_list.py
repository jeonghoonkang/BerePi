import os
import json
import requests
import urllib.parse
from io import BytesIO
from xml.etree import ElementTree
from requests.auth import HTTPBasicAuth
from PIL import Image, ExifTags



def get_env(key, default=None):
    val = os.getenv(key)
    if val is None:
        return default
    return val


NEXTCLOUD_URL = get_env('NEXTCLOUD_URL')
NEXTCLOUD_USER = get_env('NEXTCLOUD_USERNAME')
NEXTCLOUD_PASSWORD = get_env('NEXTCLOUD_PASSWORD')
PHOTO_DIR = get_env('NEXTCLOUD_PHOTO_DIR', '/Photos')

if not all([NEXTCLOUD_URL, NEXTCLOUD_USER, NEXTCLOUD_PASSWORD]):
    raise RuntimeError('NEXTCLOUD_URL, NEXTCLOUD_USERNAME, and NEXTCLOUD_PASSWORD environment variables must be set')


def parse_exif(data):
    """Return shooting date and location from image bytes."""
    try:
        img = Image.open(BytesIO(data))
        exif = img._getexif()
    except Exception:
        return None, None

    if not exif:
        return None, None

    decoded = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}

    date_taken = decoded.get('DateTimeOriginal') or decoded.get('DateTime')

    gps = decoded.get('GPSInfo')
    location = None
    if isinstance(gps, dict):
        gps_decoded = {ExifTags.GPSTAGS.get(k, k): v for k, v in gps.items()}

        def to_deg(value):
            d = value[0][0] / value[0][1]
            m = value[1][0] / value[1][1]
            s = value[2][0] / value[2][1]
            return d + (m / 60.0) + (s / 3600.0)

        try:
            lat = to_deg(gps_decoded['GPSLatitude'])
            if gps_decoded.get('GPSLatitudeRef') == 'S':
                lat *= -1
            lon = to_deg(gps_decoded['GPSLongitude'])
            if gps_decoded.get('GPSLongitudeRef') == 'W':
                lon *= -1
            location = {'latitude': lat, 'longitude': lon}
        except Exception:
            location = None

    return date_taken, location


def list_photos(current_path=""):
    url = f"{NEXTCLOUD_URL}/remote.php/dav/files/{NEXTCLOUD_USER}{PHOTO_DIR}{current_path}"
    response = requests.request(
        "PROPFIND",
        url,
        auth=HTTPBasicAuth(NEXTCLOUD_USER, NEXTCLOUD_PASSWORD),
        headers={"Depth": "1"},
        timeout=10,
    )

    if response.status_code != 207:
        raise RuntimeError(f"Error accessing Nextcloud: {response.status_code}")

    tree = ElementTree.fromstring(response.content)
    files = []

    for resp in tree.findall('{DAV:}response'):
        href = urllib.parse.unquote(resp.find('{DAV:}href').text)
        relative = href.replace(
            f"/remote.php/dav/files/{NEXTCLOUD_USER}{PHOTO_DIR}",
            "",
        ).lstrip('/')

        if not relative:
            continue

        if href.endswith('/'):
            files.extend(list_photos(f"/{relative}"))
            continue

        if not relative.lower().endswith(('.jpg', '.jpeg')):
            continue

        prop = resp.find('{DAV:}propstat/{DAV:}prop')
        last_mod = None
        size = None
        if prop is not None:
            lm = prop.find('{DAV:}getlastmodified')
            if lm is not None:
                last_mod = lm.text
            cl = prop.find('{DAV:}getcontentlength')
            if cl is not None and cl.text and cl.text.isdigit():
                size = int(cl.text)

        file_url = f"{NEXTCLOUD_URL}/remote.php/dav/files/{NEXTCLOUD_USER}{PHOTO_DIR}/{relative}"
        image_data = None
        try:
            get_resp = requests.get(
                file_url,
                auth=HTTPBasicAuth(NEXTCLOUD_USER, NEXTCLOUD_PASSWORD),
                timeout=10,
            )
            if get_resp.status_code == 200:
                image_data = get_resp.content
        except Exception:
            image_data = None

        date_taken = None
        location = None
        if image_data:
            date_taken, location = parse_exif(image_data)

        files.append({
            'path': relative,
            'last_modified': last_mod,
            'size': size,
            'date_taken': date_taken,
            'location': location,

        })

    return files


def main():
    photos = list_photos()
    print(json.dumps(photos, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
