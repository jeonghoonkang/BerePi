# Photo Intelligence

This directory contains utilities for analyzing photos. The `nc_photo_list.py`
script connects to a Nextcloud server via WebDAV and lists information about all
`jpg`/`jpeg` files in the `/Photos` directory. File metadata (path, last
modified and size) is printed along with EXIF information (shooting date and
GPS location) as JSON.

Set the following environment variables before running the script. Command line
options can override the EXIF parser and enable speed measurement:

- `NEXTCLOUD_URL` - base URL of the Nextcloud server
- `NEXTCLOUD_USERNAME` - your Nextcloud username
- `NEXTCLOUD_PASSWORD` - your password
- `NEXTCLOUD_PHOTO_DIR` (optional) - remote directory path, defaults to `/Photos`
- `EXIF_METHOD` (optional) - `pillow` or `exiftool` to select EXIF parser
- `COMPARE_SPEED` (optional) - set to `1` to measure both methods
- `PROCESSED_LOG` (optional) - path to a file that tracks processed JPEGs when
  using exiftool
- `LOCAL_PHOTO_DIR` (optional) - when using exiftool you may provide a local
  directory instead of connecting to Nextcloud. In this mode, Nextcloud
  credentials are not required.

Install the [Pillow](https://python-pillow.org/) package to enable EXIF processing or
install [exiftool](https://exiftool.org/) if you prefer to use the CLI parser.

```bash
pip install pillow
# exiftool is required when using the CLI parser
sudo apt-get install exiftool
```

Run the script with Python 3. Progress for each directory will be printed to
the console. Command line options allow selecting the EXIF parser and writing
results to a JSON file:

```bash
# default uses Pillow for EXIF
python3 nc_photo_list.py

# use exiftool and measure speed difference
python3 nc_photo_list.py --use-exiftool --compare-speed

# write the output to result.json

python3 nc_photo_list.py -o result.json

# record processed files so reruns skip them
python3 nc_photo_list.py --use-exiftool --processed-log processed.txt

# use exiftool on a local directory
python3 nc_photo_list.py --use-exiftool --local-dir ./my_photos
```

For an interactive interface using [Streamlit](https://streamlit.io/) install the
extra dependency and run the Streamlit app. The UI lets you choose the EXIF
parsing method and optionally measure both to compare speeds. You can also
specify a local directory when using exiftool so Nextcloud credentials are not
needed. The current directory being scanned is displayed as the script runs:

```bash
pip install streamlit pillow
python3 -m streamlit run nc_photo_streamlit.py
```
