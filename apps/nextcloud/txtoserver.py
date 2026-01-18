#!/usr/bin/env python3
"""
Incrementally copy photos from Nextcloud server A (source) to server B (destination)
without duplicates, using WebDAV.

Configuration is loaded from input.conf (INI format). Example:

[source]
webdav_hostname = https://nextcloud-a.example.com
webdav_root = /remote.php/dav/files/username/
port = 443
username = user_a
password = pass_a
root = Photos

[destination]
webdav_hostname = https://nextcloud-b.example.com
webdav_root = /remote.php/dav/files/username/
port = 443
username = user_b
password = pass_b
root = Photos

[settings]
verify_ssl = true

Usage:
  python3 txtoserver.py
  python3 txtoserver.py /path/to/input.conf
"""

from __future__ import annotations

import configparser
import datetime as dt
import os
import posixpath
import subprocess
import sys
import tempfile
from typing import Dict, Iterable, List, Optional, Tuple

from webdav3.client import Client
from webdav3.exceptions import WebDavException

ConfigInfo = Tuple[Optional[int], Optional[str], Optional[dt.datetime]]


def print_usage() -> None:
    print("Usage:")
    print("  python3 txtoserver.py")
    print("  python3 txtoserver.py /path/to/input.conf")
    print("  python3 txtoserver.py --conn_test")
    print("  python3 txtoserver.py /path/to/input.conf --conn_test")


def load_config(path: str) -> configparser.ConfigParser:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")
    parser = configparser.ConfigParser()
    parser.read(path)
    return parser


def build_client(section: configparser.SectionProxy, verify_ssl: bool) -> Client:
    options = {
        "webdav_hostname": section.get("webdav_hostname"),
        "webdav_root": section.get("webdav_root"),
        "webdav_login": section.get("username"),
        "webdav_password": section.get("password"),
        "verbose": False,
    }
    port = section.get("port", fallback="").strip()
    if port:
        options["webdav_port"] = int(port)
    client = Client(options)
    client.verify = verify_ssl
    return client


def normalize_root(root: str) -> str:
    root = root.strip("/")
    return root


def parse_time(value: Optional[str]) -> Optional[dt.datetime]:
    if not value:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return dt.datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def list_tree(client: Client, root: str) -> List[Dict[str, object]]:
    items: List[Dict[str, object]] = []
    queue = [root]
    while queue:
        current = queue.pop(0)
        try:
            entries = client.list(current, get_info=True)
        except WebDavException as exc:
            raise RuntimeError(f"Failed to list {current}: {exc}") from exc
        for entry in entries:
            if entry.get("path") == current:
                continue
            if entry.get("isdir"):
                queue.append(entry.get("path"))
            else:
                items.append(entry)
    return items


def build_info_map(entries: Iterable[Dict[str, object]]) -> Dict[str, ConfigInfo]:
    info_map: Dict[str, ConfigInfo] = {}
    for entry in entries:
        path = entry.get("path")
        if not isinstance(path, str):
            continue
        size = entry.get("size")
        size_int = int(size) if size is not None else None
        etag = entry.get("etag") if isinstance(entry.get("etag"), str) else None
        modified = parse_time(entry.get("modified") if isinstance(entry.get("modified"), str) else None)
        info_map[path] = (size_int, etag, modified)
    return info_map


def ensure_dirs(client: Client, path: str) -> None:
    if not path:
        return
    parts = path.strip("/").split("/")
    current = ""
    for part in parts:
        current = posixpath.join(current, part) if current else part
        if not client.check(current):
            client.mkdir(current)


def should_upload(src_info: ConfigInfo, dest_info: Optional[ConfigInfo]) -> bool:
    if dest_info is None:
        return True
    src_size, src_etag, src_mtime = src_info
    dest_size, dest_etag, dest_mtime = dest_info
    if src_size is not None and dest_size is not None and src_size != dest_size:
        return True
    if src_etag and dest_etag and src_etag != dest_etag:
        return True
    if src_mtime and dest_mtime and src_mtime > dest_mtime:
        return True
    return False


def upload_file(src_client: Client, dest_client: Client, src_path: str, dest_path: str) -> None:
    dest_dir = posixpath.dirname(dest_path)
    ensure_dirs(dest_client, dest_dir)
    with tempfile.NamedTemporaryFile(prefix="nextcloud_sync_") as tmp_file:
        src_client.download_sync(remote_path=src_path, local_path=tmp_file.name)
        dest_client.upload_sync(remote_path=dest_path, local_path=tmp_file.name)


def run_source_propfind(section: configparser.SectionProxy, root: str) -> int:
    hostname = section.get("webdav_hostname")
    webdav_root = section.get("webdav_root")
    username = section.get("username")
    password = section.get("password")
    if not hostname or not webdav_root or not username or not password:
        print("Missing source connection details for PROPFIND.")
        return 1
    propfind_url = f"{hostname.rstrip('/')}/{webdav_root.strip('/')}"
    if root:
        propfind_url = f"{propfind_url}/{root.lstrip('/')}"
    command = [
        "curl",
        "-X",
        "PROPFIND",
        "-u",
        f"{username}:{password}",
        "-H",
        "Depth: 1",
        propfind_url,
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode


def run_connection_test(client: Client, root: str, label: str) -> None:
    try:
        client.list(root, get_info=True)
    except WebDavException as exc:
        raise RuntimeError(f"Connection test failed for {label}: {exc}") from exc
    print(f"Connection test succeeded for {label}.")


def main() -> int:
    print_usage()
    args = [arg for arg in sys.argv[1:] if arg != "--conn_test"]
    conn_test = "--conn_test" in sys.argv[1:]
    config_path = args[0] if args else "input.conf"
    try:
        config = load_config(config_path)
    except FileNotFoundError as exc:
        print(exc)
        return 1

    verify_ssl = config.getboolean("settings", "verify_ssl", fallback=True)
    src_section = config["source"]
    dest_section = config["destination"]

    src_root = normalize_root(src_section.get("root", ""))
    dest_root = normalize_root(dest_section.get("root", ""))

    propfind_code = run_source_propfind(src_section, src_root)
    if propfind_code != 0:
        print(f"Source PROPFIND failed with exit code {propfind_code}.")
        return propfind_code

    src_client = build_client(src_section, verify_ssl)
    dest_client = build_client(dest_section, verify_ssl)

    if conn_test:
        try:
            run_connection_test(src_client, src_root, "source")
            run_connection_test(dest_client, dest_root, "destination")
        except RuntimeError as exc:
            print(exc)
            return 1
        return 0

    print("Scanning source server...")
    src_entries = list_tree(src_client, src_root)
    print(f"Found {len(src_entries)} files in source.")

    print("Scanning destination server...")
    dest_entries = list_tree(dest_client, dest_root)
    dest_map = build_info_map(dest_entries)

    uploaded = 0
    skipped = 0

    for entry in src_entries:
        src_path = entry.get("path")
        if not isinstance(src_path, str):
            continue
        rel_path = src_path[len(src_root):].lstrip("/") if src_root else src_path
        dest_path = posixpath.join(dest_root, rel_path) if dest_root else rel_path
        src_info = build_info_map([entry]).get(src_path, (None, None, None))
        dest_info = dest_map.get(dest_path)
        if should_upload(src_info, dest_info):
            print(f"Uploading {src_path} -> {dest_path}")
            upload_file(src_client, dest_client, src_path, dest_path)
            uploaded += 1
        else:
            skipped += 1

    print(f"Done. Uploaded: {uploaded}, Skipped: {skipped}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
