import os
import json
import requests
import urllib.parse
from io import BytesIO
from xml.etree import ElementTree
from requests.auth import HTTPBasicAuth
from PIL import Image, ExifTags
import subprocess
import traceback
import time
import re
import argparse



def get_env(key, default=None):
    val = os.getenv(key)
    if val is None:
        return default
    return val



def validate_env():
    url = get_env('NEXTCLOUD_URL')
    user = get_env('NEXTCLOUD_USERNAME')
    password = get_env('NEXTCLOUD_PASSWORD')
    photo_dir = get_env('NEXTCLOUD_PHOTO_DIR', '/Photos')
    if not all([url, user, password]):
        raise RuntimeError(
            'NEXTCLOUD_URL, NEXTCLOUD_USERNAME, and NEXTCLOUD_PASSWORD environment variables must be set'
        )
    return url, user, password, photo_dir


def parse_exif_pillow(data):
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


def _deg_to_float(coord):
    """Convert exiftool coordinate string to float degrees."""
    if coord is None:
        return None
    if isinstance(coord, (int, float)):
        return float(coord)
    if isinstance(coord, str):
        m = re.match(r"([0-9.]+) deg ([0-9.]+)' ([0-9.]+)\" ([NSEW])", coord)
        if m:
            d, m_val, s, ref = m.groups()
            deg = float(d)
            minutes = float(m_val)
            sec = float(s)
            sign = -1 if ref in ['S', 'W'] else 1
            return sign * (deg + minutes / 60.0 + sec / 3600.0)
        try:
            return float(coord)
        except Exception:
            return None
    return None


def parse_exif_exiftool(data):
    """Return shooting date and location using exiftool CLI."""
    try:
        result = subprocess.run(
            ["exiftool", "-j", "-"],
            input=data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        info = json.loads(result.stdout.decode("utf-8", errors="ignore"))[0]
    except Exception:
        return None, None

    date_taken = (
        info.get("DateTimeOriginal")
        or info.get("CreateDate")
        or info.get("ModifyDate")
    )
    lat = _deg_to_float(info.get("GPSLatitude"))
    lon = _deg_to_float(info.get("GPSLongitude"))
    location = None
    if lat is not None and lon is not None:
        location = {"latitude": lat, "longitude": lon}
    return date_taken, location


def list_photos(
    nc_url,
    username,
    password,
    photo_dir="/Photos",
    progress_cb=None,
    exif_method="pillow",
    measure_speed=False,
    processed_log=None,

):
    """Iteratively walk the photo directory and return metadata for JPEG files.

    Parameters
    ----------
    exif_method : str
        Either ``"pillow"`` or ``"exiftool"`` to select the metadata parser.
    measure_speed : bool
        If True, timings for both methods are recorded in the result.
    """

    root_prefix = f"/remote.php/dav/files/{username}{photo_dir}"
    queue = ["/"]
    seen = set()
    files = []

    processed = set()
    if processed_log and os.path.exists(processed_log):
        with open(processed_log, "r", encoding="utf-8") as f:
            processed = set(l.strip() for l in f if l.strip())

    while queue:
        current_path = queue.pop(0)
        if progress_cb:
            progress_cb(current_path)
        else:
            print(f"Scanning {photo_dir}{current_path}")

        url = f"{nc_url}{root_prefix}{current_path}"
        response = requests.request(
            "PROPFIND",
            url,
            auth=HTTPBasicAuth(username, password),
            headers={"Depth": "1"},
            timeout=10,
        )

        if response.status_code != 207:
            raise RuntimeError(
                f"Error accessing Nextcloud: {response.status_code} for {current_path}"
            )

        tree = ElementTree.fromstring(response.content)

        for resp in tree.findall('{DAV:}response'):
            href = urllib.parse.unquote(resp.find('{DAV:}href').text)
            relative = href.replace(root_prefix, "", 1).lstrip('/')

            if not relative:
                continue

            if href.endswith('/'):
                dir_path = "/" + relative
                if dir_path not in seen:
                    seen.add(dir_path)
                    queue.append(dir_path)
                continue

            if not relative.lower().endswith((".jpg", ".jpeg")):
                continue

            if relative in processed:
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

            file_url = f"{nc_url}{root_prefix}/{relative}"
            image_data = None
            try:
                get_resp = requests.get(
                    file_url,
                    auth=HTTPBasicAuth(username, password),
                    timeout=10,
                )
                if get_resp.status_code == 200:
                    image_data = get_resp.content
            except Exception:
                image_data = None

            date_taken = None
            location = None
            timing = {}
            if image_data:
                if measure_speed:
                    start = time.perf_counter()
                    dt_pillow, loc_pillow = parse_exif_pillow(image_data)
                    pillow_time = time.perf_counter() - start

                    start = time.perf_counter()
                    dt_tool, loc_tool = parse_exif_exiftool(image_data)
                    tool_time = time.perf_counter() - start

                    timing = {
                        "pillow_ms": round(pillow_time * 1000, 3),
                        "exiftool_ms": round(tool_time * 1000, 3),
                        "diff_ms": round((tool_time - pillow_time) * 1000, 3),
                    }
                    if exif_method == "exiftool":
                        date_taken, location = dt_tool, loc_tool
                    else:
                        date_taken, location = dt_pillow, loc_pillow
                else:
                    if exif_method == "exiftool":
                        date_taken, location = parse_exif_exiftool(image_data)
                    else:
                        date_taken, location = parse_exif_pillow(image_data)

            entry = {
                "path": relative,
                "last_modified": last_mod,
                "size": size,
                "date_taken": date_taken,
                "location": location,
            }
            if measure_speed and timing:
                entry.update(timing)
            files.append(entry)

            if processed_log and (exif_method == "exiftool" or measure_speed):
                if relative not in processed:
                    processed.add(relative)
                    with open(processed_log, "a", encoding="utf-8") as f:
                        f.write(relative + "\n")


    return files


def main():
    parser = argparse.ArgumentParser(description="List Nextcloud photos")
    parser.add_argument(
        "-o",
        "--output",
        help="write JSON result to file instead of stdout",
    )
    parser.add_argument(
        "--use-exiftool",
        action="store_true",
        help="parse EXIF using exiftool",
    )
    parser.add_argument(
        "--compare-speed",
        action="store_true",
        help="measure time difference between Pillow and exiftool",
    )
    parser.add_argument(
        "--processed-log",
        help="file to track processed JPEGs when using exiftool",
    )

    args = parser.parse_args()

    url, user, password, photo_dir = validate_env()
    exif_method = (
        "exiftool" if args.use_exiftool else get_env("EXIF_METHOD", "pillow").lower()
    )
    measure_speed = args.compare_speed or get_env("COMPARE_SPEED", "0") == "1"
    processed_log = args.processed_log or get_env("PROCESSED_LOG")


    try:
        photos = list_photos(
            url,
            user,
            password,
            photo_dir,
            exif_method=exif_method,
            measure_speed=measure_speed,
            processed_log=processed_log,

        )
        result = json.dumps(photos, indent=2, ensure_ascii=False)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(result)
        else:
            print(result)
    except Exception:
        traceback.print_exc()

if __name__ == '__main__':
    main()
