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
import hashlib
import os
import posixpath
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from webdav3.client import Client
from webdav3.exceptions import WebDavException

ConfigInfo = Tuple[Optional[int], Optional[str], Optional[dt.datetime]]
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR / "input.conf"
DEFAULT_SKIP_LOG = SCRIPT_DIR / "skip.txt"

COLOR_RESET = "\033[0m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"


@dataclass
class Progress:
    total_files: int = 0
    total_bytes: int = 0
    completed_files: int = 0
    completed_bytes: int = 0


def color_text(color: str, text: str) -> str:
    return f"{color}{text}{COLOR_RESET}"


def format_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{size} B"


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

SUCCESS_COLOR = "\033[1;32m"
HIGHLIGHT_COLOR = "\033[1;33m"
RESET_COLOR = "\033[0m"


def highlight_label(label: str) -> str:
    if label.lower() in {"source", "destination"}:
        return f"{HIGHLIGHT_COLOR}{label}{SUCCESS_COLOR}"
    return label


def print_usage() -> None:
    print("Usage:")
    print("  python3 txtoserver.py")
    print("  python3 txtoserver.py /path/to/input.conf")
    print("  python3 txtoserver.py --conn_test")
    print("  python3 txtoserver.py /path/to/input.conf --conn_test")
    print(f"Default config path: {DEFAULT_CONFIG}")


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


def list_tree(client: Client, root: str) -> List[Dict[str, object]]:
    items: List[Dict[str, object]] = []
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
            else:
                normalized_entry = dict(entry)
                normalized_entry["path"] = (
                    posixpath.join(normalized_root, entry_rel) if normalized_root else entry_rel
                )
                items.append(normalized_entry)
    return items


def build_info_map(entries: Iterable[Dict[str, object]]) -> Dict[str, ConfigInfo]:
    info_map: Dict[str, ConfigInfo] = {}
    for entry in entries:
        path = entry.get("path")
        if not isinstance(path, str):
            continue
        normalized_path = normalize_remote_path(path)
        size = entry.get("size")
        size_int = int(size) if size is not None else None
        etag = entry.get("etag") if isinstance(entry.get("etag"), str) else None
        modified = parse_time(entry.get("modified") if isinstance(entry.get("modified"), str) else None)
        info_map[normalized_path] = (size_int, etag, modified)
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
    plain_message = f" Connection test succeeded for {label}. "
    message = f" Connection test succeeded for {highlight_label(label)}. "
    border = "+" + "-" * len(plain_message) + "+"
    print(f"{SUCCESS_COLOR}{border}")
    print(f"|{message}|")
    print(f"{border}{RESET_COLOR}")


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


def append_skip_log(skip_file: str, src_url: str, dst_url: str) -> None:
    with open(skip_file, "a", encoding="utf-8") as file:
        file.write(f"src={src_url} | dst={dst_url}\n")


def get_entry_size(entry: Dict[str, object]) -> int:
    size = entry.get("size")
    if size is None:
        return 0
    try:
        return int(size)
    except (TypeError, ValueError):
        return 0


def print_transfer_summary(progress: Progress) -> None:
    print(f"전송 대상: 파일 {progress.total_files}개, 용량 {format_bytes(progress.total_bytes)}")
    print(
        "전송 완료: "
        f"파일 {progress.completed_files}/{progress.total_files}개, "
        f"용량 {format_bytes(progress.completed_bytes)}/{format_bytes(progress.total_bytes)}"
    )


def upload_and_verify_file(
    src_client: Client,
    dest_client: Client,
    src_path: str,
    dest_path: str,
) -> int:
    dest_dir = posixpath.dirname(dest_path)
    ensure_dirs(dest_client, dest_dir)
    with tempfile.NamedTemporaryFile(prefix="nextcloud_src_") as src_tmp, tempfile.NamedTemporaryFile(
        prefix="nextcloud_dst_"
    ) as dest_tmp:
        src_client.download_sync(remote_path=src_path, local_path=src_tmp.name)
        src_hash = sha256_file(src_tmp.name)
        src_size = os.path.getsize(src_tmp.name)

        dest_client.upload_sync(remote_path=dest_path, local_path=src_tmp.name)
        dest_client.download_sync(remote_path=dest_path, local_path=dest_tmp.name)
        dest_hash = sha256_file(dest_tmp.name)
        dest_size = os.path.getsize(dest_tmp.name)

    if src_size != dest_size or src_hash != dest_hash:
        raise RuntimeError(
            "Verification failed after upload: "
            f"{src_path} -> {dest_path} "
            f"(src_size={src_size}, dest_size={dest_size})"
        )
    return src_size


def main() -> int:
    print_usage()
    args = [arg for arg in sys.argv[1:] if arg != "--conn_test"]
    conn_test = "--conn_test" in sys.argv[1:]
    config_path = args[0] if args else str(DEFAULT_CONFIG)
    try:
        config = load_config(config_path)
    except FileNotFoundError as exc:
        print(exc)
        print(color_text(COLOR_RED, "종료 상태: 실패"))
        return 1

    verify_ssl = config.getboolean("settings", "verify_ssl", fallback=True)
    src_section = config["source"]
    dest_section = config["destination"]

    src_root = normalize_root(src_section.get("root", ""))
    dest_root = normalize_root(dest_section.get("root", ""))

    validate_paths(src_section, src_root, "Source")
    validate_paths(dest_section, dest_root, "Destination")

    propfind_code = run_source_propfind(src_section, src_root)
    if propfind_code != 0:
        print(f"Source PROPFIND failed with exit code {propfind_code}.")
        print(color_text(COLOR_RED, "종료 상태: 실패"))
        return propfind_code

    src_client = build_client(src_section, verify_ssl)
    dest_client = build_client(dest_section, verify_ssl)

    if conn_test:
        try:
            run_connection_test(src_client, src_root, "source")
            run_connection_test(dest_client, dest_root, "destination")
        except RuntimeError as exc:
            print(exc)
            print(color_text(COLOR_RED, "종료 상태: 실패"))
            return 1
        print(color_text(COLOR_GREEN, "종료 상태: 성공"))
        return 0

    print("Scanning source server...")
    src_entries = list_tree(src_client, src_root)
    print(f"Found {len(src_entries)} files in source.")
    src_map = build_info_map(src_entries)

    print("Scanning destination server...")
    dest_entries = list_tree(dest_client, dest_root)
    dest_map = build_info_map(dest_entries)

    uploaded = 0
    skipped = 0
    failed = 0
    skip_file = str(DEFAULT_SKIP_LOG)
    progress = Progress()

    for entry in src_entries:
        src_path = entry.get("path")
        if not isinstance(src_path, str):
            continue
        normalized_src_path = normalize_remote_path(src_path)
        rel_path = relative_from_root(src_path, src_root)
        if rel_path is None:
            print(
                "Skipping unexpected source path "
                f"'{src_path}' (normalized='{normalized_src_path}'), root='{src_root}'"
            )
            skipped += 1
            continue
        dest_path = posixpath.join(dest_root, rel_path) if dest_root else rel_path
        src_info = src_map.get(normalized_src_path, (None, None, None))
        dest_info = dest_map.get(normalize_remote_path(dest_path))
        if should_upload(src_info, dest_info):
            progress.total_files += 1
            progress.total_bytes += get_entry_size(entry)
    print_transfer_summary(progress)

    for entry in src_entries:
        src_path = entry.get("path")
        if not isinstance(src_path, str):
            continue
        normalized_src_path = normalize_remote_path(src_path)
        rel_path = relative_from_root(src_path, src_root)
        if rel_path is None:
            print(
                "Skipping unexpected source path "
                f"'{src_path}' (normalized='{normalized_src_path}'), root='{src_root}'"
            )
            skipped += 1
            continue
        dest_path = posixpath.join(dest_root, rel_path) if dest_root else rel_path
        src_info = src_map.get(normalized_src_path, (None, None, None))
        dest_info = dest_map.get(normalize_remote_path(dest_path))
        if should_upload(src_info, dest_info):
            print(f"Uploading {src_path} -> {dest_path}")
            try:
                transferred_size = upload_and_verify_file(src_client, dest_client, src_path, dest_path)
            except RuntimeError as exc:
                print(color_text(COLOR_RED, f"FAILED: {exc}"))
                failed += 1
                continue
            uploaded += 1
            progress.completed_files += 1
            progress.completed_bytes += transferred_size
            print_transfer_summary(progress)
        else:
            src_url = compose_remote_url(src_section, src_path)
            dst_url = compose_remote_url(dest_section, dest_path)
            append_skip_log(skip_file, src_url, dst_url)
            print(f"Skipping existing file: {src_url} -> {dst_url}")
            skipped += 1

    print(f"Done. Uploaded: {uploaded}, Skipped: {skipped}, Failed: {failed}.")
    if failed:
        print(color_text(COLOR_RED, "종료 상태: 실패"))
        return 1
    if uploaded == 0:
        print(color_text(COLOR_YELLOW, "종료 상태: 전송할 파일 없음"))
        return 0
    print(color_text(COLOR_GREEN, "종료 상태: 성공"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
