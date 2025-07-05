# Photo Intelligence

This directory contains utilities for analyzing photos. The `nc_photo_list.py`
script connects to a Nextcloud server via WebDAV and lists information about all
`jpg`/`jpeg` files in the `/Photos` directory. File metadata (path, last
modified and size) is printed along with EXIF information (shooting date and
GPS location) as JSON.

Set the following environment variables before running the script:

- `NEXTCLOUD_URL` - base URL of the Nextcloud server
- `NEXTCLOUD_USERNAME` - your Nextcloud username
- `NEXTCLOUD_PASSWORD` - your password
- `NEXTCLOUD_PHOTO_DIR` (optional) - remote directory path, defaults to `/Photos`

Install the [Pillow](https://python-pillow.org/) package to enable EXIF processing:

```bash
pip install pillow
```

Run the script with Python 3. Progress for each directory will be printed to
the console:

```bash
python3 nc_photo_list.py
```

For an interactive interface using [Streamlit](https://streamlit.io/) install the
extra dependency and run the Streamlit app. The current directory being scanned
is displayed as the script runs:

```bash
pip install streamlit pillow
python3 -m streamlit run nc_photo_streamlit.py
```
