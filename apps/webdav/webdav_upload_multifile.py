#!/usr/bin/env python3
"""Upload multiple local files to a WebDAV server.

Configuration is loaded from `.evn_webdav` first and then `.env_webdav`.

Example:
  python3 webdav_upload_multifile.py -f file1.jpg file2.jpg file3.jpg
  python3 webdav_upload_multifile.py -f `ls /var/lib/motion | tail -50`
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Iterable

import requests


CONFIG_CANDIDATES = (".evn_webdav", ".env_webdav")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload multiple files to WebDAV.")
    parser.add_argument(
        "-f",
        "--file",
        nargs="+",
        required=True,
        help="One or more local file paths to upload.",
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
        script_dir.parent.parent,
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
    raise KeyError(f"Missing required config key: {', '.join(keys)}")


def build_remote_url(config: Dict[str, str], remote_name: str) -> str:
    hostname = require(config, "WEBDAV_URL", "WEBDAV_HOST", "WEBDAV_HOSTNAME").rstrip("/")
    if hostname.startswith(("http://", "https://")):
        base_url = hostname
    else:
        scheme = config.get("WEBDAV_SCHEME", "https").strip()
        port = config.get("WEBDAV_PORT", "").strip()
        base_url = f"{scheme}://{hostname}:{port}" if port else f"{scheme}://{hostname}"

    root = config.get("WEBDAV_ROOT", "").strip().strip("/")
    return f"{base_url}/{root}/{remote_name}" if root else f"{base_url}/{remote_name}"


def resolve_files(file_args: Iterable[str]) -> list[Path]:
    resolved_files: list[Path] = []
    for item in file_args:
        path = Path(item).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        else:
            path = path.resolve()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if not path.is_file():
            raise ValueError(f"Not a file: {path}")
        resolved_files.append(path)
    return resolved_files


def upload_one(
    file_path: Path,
    remote_url: str,
    username: str,
    password: str,
    verify_ssl: bool,
) -> int:
    with file_path.open("rb") as handle:
        response = requests.put(
            remote_url,
            data=handle,
            auth=(username, password),
            verify=verify_ssl,
            timeout=300,
        )

    print(f"local : {file_path}")
    print(f"remote: {remote_url}")
    print(f"status: {response.status_code}")

    if response.ok:
        return 0

    print(response.text[:500], file=sys.stderr)
    return 1


def main() -> int:
    args = parse_args()
    config_path = find_config_file()
    config = parse_env_file(config_path)

    username = require(config, "WEBDAV_USER", "WEBDAV_LOGIN", "WEBDAV_USERNAME")
    password = require(config, "WEBDAV_PASSWORD", "WEBDAV_PW")
    verify_ssl = as_bool(config.get("WEBDAV_VERIFY_SSL"), default=True)
    files = resolve_files(args.file)

    print(f"config: {config_path}")
    print(f"count : {len(files)}")

    failed = 0
    for file_path in files:
        remote_url = build_remote_url(config, file_path.name)
        try:
            failed += upload_one(file_path, remote_url, username, password, verify_ssl)
        except requests.RequestException as exc:
            failed += 1
            print(f"Upload failed for {file_path}: {exc}", file=sys.stderr)

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
