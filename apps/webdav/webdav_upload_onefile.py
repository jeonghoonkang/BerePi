#!/usr/bin/env python3
"""Upload a single local file to a WebDAV server.

Configuration is loaded from `.evn_webdav` first and then `.env_webdav`.
Supported keys:

  WEBDAV_SCHEME=https
  WEBDAV_HOST=example.com
  WEBDAV_PORT=443
  WEBDAV_USER=username
  WEBDAV_PASSWORD=password
  WEBDAV_ROOT=/remote.php/dav/files/username/path
  WEBDAV_VERIFY_SSL=true

Example:
  python3 webdav_upload_onefile.py -f image.jpg
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict

import requests


CONFIG_CANDIDATES = (".evn_webdav", ".env_webdav")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload one file to WebDAV.")
    parser.add_argument(
        "-f",
        "--file",
        required=True,
        help="Local file path to upload.",
    )
    parser.add_argument(
        "-n",
        "--remote-name",
        help="Remote filename override. Defaults to the local basename.",
    )
    return parser.parse_args()


def parse_env_file(path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        data[key.strip()] = value
    return data


def find_config_file() -> Path:
    script_dir = Path(__file__).resolve().parent
    search_dirs = [
        Path.cwd(),
        script_dir,
        script_dir.parent,
        script_dir / "webdav",
    ]
    seen = set()
    for directory in search_dirs:
        resolved = directory.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        for candidate in CONFIG_CANDIDATES:
            candidate_path = resolved / candidate
            if candidate_path.exists():
                return candidate_path
    raise FileNotFoundError(
        "Could not find .evn_webdav or .env_webdav in the current directory or script locations."
    )


def as_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def require(config: Dict[str, str], *keys: str) -> str:
    for key in keys:
        value = config.get(key)
        if value:
            return value
    joined = ", ".join(keys)
    raise KeyError(f"Missing required config key: {joined}")


def build_remote_url(config: Dict[str, str], remote_name: str) -> str:
    hostname = require(config, "WEBDAV_URL", "WEBDAV_HOST", "WEBDAV_HOSTNAME").rstrip("/")
    if hostname.startswith("http://") or hostname.startswith("https://"):
        base_url = hostname
    else:
        scheme = config.get("WEBDAV_SCHEME", "https").strip()
        port = config.get("WEBDAV_PORT", "").strip()
        if port:
            base_url = f"{scheme}://{hostname}:{port}"
        else:
            base_url = f"{scheme}://{hostname}"

    root = config.get("WEBDAV_ROOT", "").strip().strip("/")
    if root:
        return f"{base_url}/{root}/{remote_name}"
    return f"{base_url}/{remote_name}"


def upload_file(file_path: Path, remote_name: str) -> int:
    config_path = find_config_file()
    config = parse_env_file(config_path)

    username = require(config, "WEBDAV_USER", "WEBDAV_LOGIN", "WEBDAV_USERNAME")
    password = require(config, "WEBDAV_PASSWORD", "WEBDAV_PW")
    verify_ssl = as_bool(config.get("WEBDAV_VERIFY_SSL"), default=True)
    remote_url = build_remote_url(config, remote_name)

    with file_path.open("rb") as handle:
        response = requests.put(
            remote_url,
            data=handle,
            auth=(username, password),
            verify=verify_ssl,
            timeout=300,
        )

    print(f"config: {config_path}")
    print(f"local : {file_path}")
    print(f"remote: {remote_url}")
    print(f"status: {response.status_code}")

    if response.ok:
        return 0

    print(response.text[:500], file=sys.stderr)
    return 1


def main() -> int:
    args = parse_args()
    file_path = Path(args.file).expanduser().resolve()
    if not file_path.exists():
        print(f"File not found: {file_path}", file=sys.stderr)
        return 1
    if not file_path.is_file():
        print(f"Not a file: {file_path}", file=sys.stderr)
        return 1

    remote_name = args.remote_name or file_path.name
    try:
        return upload_file(file_path, remote_name)
    except (FileNotFoundError, KeyError, requests.RequestException) as exc:
        print(f"Upload failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
