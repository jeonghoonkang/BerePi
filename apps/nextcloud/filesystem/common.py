#!/usr/bin/env python3

from __future__ import annotations

import configparser
import datetime as dt
import os
import posixpath
import subprocess
from typing import Dict, List, Optional

from webdav3.client import Client
from webdav3.exceptions import WebDavException

EntryInfo = Dict[str, object]

SUCCESS_COLOR = "\033[1;32m"
HIGHLIGHT_COLOR = "\033[1;33m"
RESET_COLOR = "\033[0m"


def highlight_label(label: str) -> str:
    if label.lower() == "target":
        return f"{HIGHLIGHT_COLOR}{label}{SUCCESS_COLOR}"
    return label


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
    plain_message = f" Connection test succeeded for {label}. "
    message = f" Connection test succeeded for {highlight_label(label)}. "
    border = "+" + "-" * len(plain_message) + "+"
    print(f"{SUCCESS_COLOR}{border}")
    print(f"|{message}|")
    print(f"{border}{RESET_COLOR}")


def validate_paths(section: configparser.SectionProxy, root: str, label: str) -> str:
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
