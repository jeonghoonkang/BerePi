# Photo Intelligence

This directory contains utilities for analyzing photos. The `nc_photo_list.py`
script connects to a Nextcloud server via WebDAV and lists information about all
`jpg`/`jpeg` files in the `/Photos` directory. File metadata (path, last modified
and size) is printed as JSON.

Set the following environment variables before running the script:

- `NEXTCLOUD_URL` - base URL of the Nextcloud server
- `NEXTCLOUD_USERNAME` - your Nextcloud username
- `NEXTCLOUD_PASSWORD` - your password
- `NEXTCLOUD_PHOTO_DIR` (optional) - remote directory path, defaults to `/Photos`

Run the script with Python 3:

```bash
python3 nc_photo_list.py
```
