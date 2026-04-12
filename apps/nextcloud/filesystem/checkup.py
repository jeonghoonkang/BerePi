#!/usr/bin/env python3
"""
Inspect remote Nextcloud directories over WebDAV.

Configuration is loaded from input.conf (INI format).

[target]
webdav_hostname = https://nextcloud-a.example.com
webdav_root = /remote.php/dav/files/username/
port = 443
username = user_a
password = pass_a
root = Photos

[settings]
verify_ssl = true

Usage:
  python3 checkup.py
  python3 checkup.py /path/to/input.conf
  python3 checkup.py checkup.sample.conf
  python3 checkup.py --conn_test
"""

from __future__ import annotations

import datetime as dt
import sys
from typing import Dict, List, Optional, Tuple

from common import (
    EntryInfo,
    build_client,
    compose_remote_url,
    format_bytes,
    format_time,
    list_tree,
    load_config,
    normalize_root,
    parse_time,
    run_connection_test,
    run_propfind,
    validate_paths,
)

SectionStats = Dict[str, object]


def print_usage() -> None:
    print("Usage:")
    print("  python3 checkup.py")
    print("  python3 checkup.py /path/to/input.conf")
    print("  python3 checkup.py checkup.sample.conf")
    print("  python3 checkup.py --conn_test")
    print("  python3 checkup.py /path/to/input.conf --conn_test")


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


def print_stats(label: str, section, root: str, stats: SectionStats) -> None:
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


def parse_args(argv: List[str]) -> Tuple[str, bool]:
    args = list(argv)
    conn_test = False
    config_path = "input.conf"
    positional: List[str] = []

    for arg in args:
        if arg == "--conn_test":
            conn_test = True
        elif arg in {"-h", "--help"}:
            print_usage()
            raise SystemExit(0)
        else:
            positional.append(arg)

    if positional:
        config_path = positional[0]
    if len(positional) > 1:
        raise ValueError("Too many positional arguments.")
    return config_path, conn_test


def main() -> int:
    print_usage()
    try:
        config_path, conn_test = parse_args(sys.argv[1:])
        config = load_config(config_path)
    except (FileNotFoundError, ValueError) as exc:
        print(exc)
        return 1

    verify_ssl = config.getboolean("settings", "verify_ssl", fallback=True)
    try:
        section = config["target"]
    except KeyError as exc:
        print(f"Missing config section(s): {exc}")
        return 1

    root = normalize_root(section.get("root", ""))
    label = "Target"
    validate_paths(section, root, label)

    propfind_code = run_propfind(section, root)
    if propfind_code != 0:
        print(f"{label} PROPFIND failed with exit code {propfind_code}.")
        return propfind_code

    client = build_client(section, verify_ssl)

    if conn_test:
        try:
            run_connection_test(client, root, "target")
        except RuntimeError as exc:
            print(exc)
            return 1
        return 0

    print("Scanning target server...")
    entries = list_tree(client, root)
    stats = build_stats(entries)
    print_stats(label, section, root, stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
