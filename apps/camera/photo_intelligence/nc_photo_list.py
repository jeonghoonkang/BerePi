import os
import json
import requests
import urllib.parse
from xml.etree import ElementTree
from requests.auth import HTTPBasicAuth


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

        files.append({
            'path': relative,
            'last_modified': last_mod,
            'size': size,
        })

    return files


def main():
    photos = list_photos()
    print(json.dumps(photos, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
