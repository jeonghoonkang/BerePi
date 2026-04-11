#!/usr/bin/env python3
"""
Inspect remote Nextcloud directories over WebDAV.

Configuration is loaded from input.conf (INI format). It follows the same
layout used by txtoserver.py:

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
  python3 checkup.py
  python3 checkup.py /path/to/input.conf
  python3 checkup.py checkup.sample.conf
  python3 checkup.py --conn_test
  python3 checkup.py --section source
  python3 checkup.py /path/to/input.conf --section destination
"""

from __future__ import annotations

import configparser
import datetime as dt
import os
import posixpath
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

from webdav3.client import Client
from webdav3.exceptions import WebDavException

EntryInfo = Dict[str, object]
SectionStats = Dict[str, object]


def print_usage() -> None:
    print("Usage:")
    print("  python3 checkup.py")
    print("  python3 checkup.py /path/to/input.conf")
    print("  python3 checkup.py checkup.sample.conf")
    print("  python3 checkup.py --conn_test")
    print("  python3 checkup.py /path/to/input.conf --conn_test")
    print("  python3 checkup.py --section source")
    print("  python3 checkup.py /path/to/input.conf --section destination")


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
    return root.strip("/")


def normalize_remote_path(path: str) -> str:
    return path.strip("/")


def relative_from_root(src_path: str, src_root: str) -> Optional[str]:
    normalized_path = normalize_remote_path(src_path)
    if not src_root:
        return normalized_path

    root_prefix = f"{src_root}/"
    if normalized_path == src_root:
        return ""
    if normalized_path.startswith(root_prefix):
        return normalized_path[len(root_prefix):]

    marker = f"/{root_prefix}"
    marker_index = normalized_path.find(marker)
    if marker_index >= 0:
        return normalized_path[marker_index + len(marker):]
    return None


def is_directory(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def parse_time(value: Optional[str]) -> Optional[dt.datetime]:
    if not value:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return dt.datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def list_tree(client: Client, root: str) -> List[EntryInfo]:
    items: List[EntryInfo] = []
    queue = [root]
    normalized_root = normalize_remote_path(root)
    while queue:
        current = queue.pop(0)
        try:
            entries = client.list(current, get_info=True)
        except WebDavException as exc:
            raise RuntimeError(f"Failed to list {current}: {exc}") from exc
        for entry in entries:
            entry_path = entry.get("path")
            if isinstance(entry_path, str) and normalize_remote_path(entry_path) == normalize_remote_path(current):
                continue
            if not isinstance(entry_path, str):
                continue

            entry_rel = relative_from_root(entry_path, normalized_root)
            if entry_rel is None:
                continue

            if is_directory(entry.get("isdir")):
                next_dir = posixpath.join(normalized_root, entry_rel) if normalized_root else entry_rel
                queue.append(next_dir)
                continue

            normalized_entry = dict(entry)
            normalized_entry["path"] = (
                posixpath.join(normalized_root, entry_rel) if normalized_root else entry_rel
            )
            items.append(normalized_entry)
    return items


def compose_remote_url(section: configparser.SectionProxy, remote_path: str) -> str:
    hostname = section.get("webdav_hostname", "").rstrip("/")
    webdav_root = section.get("webdav_root", "").strip("/")
    normalized_path = normalize_remote_path(remote_path)
    if webdav_root and normalized_path:
        return f"{hostname}/{webdav_root}/{normalized_path}"
    if webdav_root:
        return f"{hostname}/{webdav_root}"
    if normalized_path:
        return f"{hostname}/{normalized_path}"
    return hostname


def run_propfind(section: configparser.SectionProxy, root: str, depth: int = 1) -> int:
    hostname = section.get("webdav_hostname")
    webdav_root = section.get("webdav_root")
    username = section.get("username")
    password = section.get("password")
    if not hostname or not webdav_root or not username or not password:
        print("Missing connection details for PROPFIND.")
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
        f"Depth: {depth}",
        propfind_url,
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.stdout:
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


def validate_paths(
    section: configparser.SectionProxy,
    root: str,
    label: str,
) -> str:
    hostname = section.get("webdav_hostname", "")
    webdav_root = section.get("webdav_root", "")
    full_path = f"{hostname.rstrip('/')}/{webdav_root.strip('/')}"
    if root:
        full_path = f"{full_path}/{root.lstrip('/')}"
    print(f"{label} path check:")
    print(f"  webdav_hostname = {hostname}")
    print(f"  webdav_root = {webdav_root}")
    print(f"  root = {root}")
    print(f"  composed = {full_path}")
    return full_path


def format_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    value = float(size)
    unit_index = 0
    while value >= 1024 and unit_index < len(units) - 1:
        value /= 1024.0
        unit_index += 1
    return f"{value:.2f} {units[unit_index]}"


def format_time(value: Optional[dt.datetime]) -> str:
    if value is None:
        return "N/A"
    return value.isoformat(sep=" ", timespec="seconds")


def build_stats(entries: List[EntryInfo]) -> SectionStats:
    total_size = 0
    oldest_entry: Optional[Tuple[str, dt.datetime]] = None
    newest_entry: Optional[Tuple[str, dt.datetime]] = None
    undated_files = 0

    for entry in entries:
        path = entry.get("path")
        if not isinstance(path, str):
            continue

        size_value = entry.get("size")
        try:
            size = int(size_value) if size_value is not None else 0
        except (TypeError, ValueError):
            size = 0
        total_size += size

        modified = parse_time(entry.get("modified") if isinstance(entry.get("modified"), str) else None)
        if modified is None:
            undated_files += 1
            continue

        if oldest_entry is None or modified < oldest_entry[1]:
            oldest_entry = (path, modified)
        if newest_entry is None or modified > newest_entry[1]:
            newest_entry = (path, modified)

    return {
        "file_count": len(entries),
        "total_size": total_size,
        "oldest_entry": oldest_entry,
        "newest_entry": newest_entry,
        "undated_files": undated_files,
    }


def print_stats(label: str, section: configparser.SectionProxy, root: str, stats: SectionStats) -> None:
    print(f"[{label}]")
    print(f"  root: {root or '/'}")
    print(f"  url: {compose_remote_url(section, root)}")
    print(f"  file_count: {stats['file_count']}")
    print(f"  total_size: {stats['total_size']} bytes ({format_bytes(int(stats['total_size']))})")
    print(f"  undated_files: {stats['undated_files']}")

    oldest_entry = stats["oldest_entry"]
    newest_entry = stats["newest_entry"]

    if oldest_entry is None:
        print("  oldest_file_time: N/A")
        print("  oldest_file_path: N/A")
    else:
        print(f"  oldest_file_time: {format_time(oldest_entry[1])}")
        print(f"  oldest_file_path: {oldest_entry[0]}")

    if newest_entry is None:
        print("  newest_file_time: N/A")
        print("  newest_file_path: N/A")
    else:
        print(f"  newest_file_time: {format_time(newest_entry[1])}")
        print(f"  newest_file_path: {newest_entry[0]}")


def parse_args(argv: List[str]) -> Tuple[str, bool, str]:
    args = list(argv)
    conn_test = False
    section_name = "all"
    config_path = "input.conf"
    positional: List[str] = []

    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--conn_test":
            conn_test = True
        elif arg == "--section":
            index += 1
            if index >= len(args):
                raise ValueError("--section requires one of: source, destination, all")
            section_name = args[index].strip().lower()
        elif arg in {"-h", "--help"}:
            print_usage()
            raise SystemExit(0)
        else:
            positional.append(arg)
        index += 1

    if positional:
        config_path = positional[0]
    if len(positional) > 1:
        raise ValueError("Too many positional arguments.")
    if section_name not in {"source", "destination", "all"}:
        raise ValueError("--section requires one of: source, destination, all")
    return config_path, conn_test, section_name


def target_sections(
    config: configparser.ConfigParser,
    section_name: str,
) -> List[Tuple[str, configparser.SectionProxy]]:
    if section_name == "all":
        names = [name for name in ("source", "destination") if name in config]
    else:
        names = [section_name]

    missing = [name for name in names if name not in config]
    if missing:
        raise KeyError(f"Missing config section(s): {', '.join(missing)}")

    return [(name, config[name]) for name in names]


def main() -> int:
    print_usage()
    try:
        config_path, conn_test, section_name = parse_args(sys.argv[1:])
        config = load_config(config_path)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        print(exc)
        return 1

    verify_ssl = config.getboolean("settings", "verify_ssl", fallback=True)

    try:
        sections = target_sections(config, section_name)
    except KeyError as exc:
        print(exc)
        return 1

    for name, section in sections:
        root = normalize_root(section.get("root", ""))
        label = name.capitalize()
        validate_paths(section, root, label)

        propfind_code = run_propfind(section, root)
        if propfind_code != 0:
            print(f"{label} PROPFIND failed with exit code {propfind_code}.")
            return propfind_code

        client = build_client(section, verify_ssl)

        if conn_test:
            try:
                run_connection_test(client, root, name)
            except RuntimeError as exc:
                print(exc)
                return 1
            continue

        print(f"Scanning {label.lower()} server...")
        entries = list_tree(client, root)
        stats = build_stats(entries)
        print_stats(label, section, root, stats)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
