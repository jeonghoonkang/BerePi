#!/usr/bin/env python3
"""Compatibility wrapper for the historical typo in the script name."""

from webdav_upload_onefile import main


if __name__ == "__main__":
    raise SystemExit(main())
