#!/usr/bin/env python3
"""
Copy local files or directories to a Nextcloud WebDAV destination.

Configuration is loaded from copytowebav.conf (INI format). Example:

[source]
path = /data/photos

[destination]
webdav_hostname = https://nextcloud.example.com
webdav_root = /remote.php/dav/files/username/
port = 443
username = user
password = app_password
root = Backup/Photos

[settings]
verify_ssl = true

Usage:
  python3 copytowebav.py
  python3 copytowebav.py /path/to/copytowebav.conf
  python3 copytowebav.py --conn_test
  python3 copytowebav.py /path/to/copytowebav.conf --conn_test
"""

from __future__ import annotations

import configparser
import datetime as dt
import hashlib
import os
import posixpath
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from webdav3.client import Client
from webdav3.exceptions import WebDavException

ConfigInfo = Tuple[Optional[int], Optional[str], Optional[dt.datetime]]
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR / "copytowebav.conf"
DEFAULT_SKIP_LOG = SCRIPT_DIR / "copytowebav_skip.txt"

COLOR_RESET = "\033[0m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
SUCCESS_COLOR = "\033[1;32m"
HIGHLIGHT_COLOR = "\033[1;33m"
RESET_COLOR = "\033[0m"


@dataclass
class Progress:
    total_files: int = 0
    total_bytes: int = 0
    completed_files: int = 0
    completed_bytes: int = 0


def color_text(color: str, text: str) -> str:
    return f"{color}{text}{COLOR_RESET}"


def highlight_label(label: str) -> str:
    if label.lower() in {"source", "destination"}:
        return f"{HIGHLIGHT_COLOR}{label}{SUCCESS_COLOR}"
    return label


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


def print_usage() -> None:
    print("Usage:")
    print("  python3 copytowebav.py")
    print("  python3 copytowebav.py /path/to/copytowebav.conf")
    print("  python3 copytowebav.py --conn_test")
    print("  python3 copytowebav.py /path/to/copytowebav.conf --conn_test")
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
    return root.strip("/")


def normalize_remote_path(path: str) -> str:
    return path.strip("/")


def normalize_local_path(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))


def build_date_directory_name(created_at: Optional[dt.datetime] = None) -> str:
    timestamp = created_at or dt.datetime.now().astimezone()
    return timestamp.strftime("%Y-%m%d")


def build_dated_root(root: str, created_at: Optional[dt.datetime] = None) -> str:
    date_dir = build_date_directory_name(created_at)
    return posixpath.join(root, date_dir) if root else date_dir


def parse_time(value: Optional[str]) -> Optional[dt.datetime]:
    if not value:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return dt.datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def is_directory(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


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
            entry_rel = relative_remote_path(entry_path, normalized_root)
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


def relative_remote_path(path: str, root: str) -> Optional[str]:
    normalized_path = normalize_remote_path(path)
    if not root:
        return normalized_path
    root_prefix = f"{root}/"
    if normalized_path == root:
        return ""
    if normalized_path.startswith(root_prefix):
        return normalized_path[len(root_prefix):]
    marker = f"/{root_prefix}"
    marker_index = normalized_path.find(marker)
    if marker_index >= 0:
        return normalized_path[marker_index + len(marker):]
    return None


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
    src_size, _, src_mtime = src_info
    dest_size, dest_etag, dest_mtime = dest_info
    if src_size is not None and dest_size is not None and src_size != dest_size:
        return True
    if src_mtime and dest_mtime and src_mtime > dest_mtime:
        return True
    if dest_etag is None:
        return True
    return False


def append_skip_log(skip_file: str, src_path: str, dst_url: str) -> None:
    with open(skip_file, "a", encoding="utf-8") as file:
        file.write(f"src={src_path} | dst={dst_url}\n")


def print_transfer_summary(progress: Progress) -> None:
    print(f"전송 대상: 파일 {progress.total_files}개, 용량 {format_bytes(progress.total_bytes)}")
    print(
        "전송 완료: "
        f"파일 {progress.completed_files}/{progress.total_files}개, "
        f"용량 {format_bytes(progress.completed_bytes)}/{format_bytes(progress.total_bytes)}"
    )


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


def get_local_files(source_path: str) -> List[Dict[str, object]]:
    files: List[Dict[str, object]] = []
    path_obj = Path(source_path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Source path not found: {source_path}")

    if path_obj.is_file():
        stat = path_obj.stat()
        files.append(
            {
                "path": str(path_obj),
                "relative_path": path_obj.name,
                "size": stat.st_size,
                "modified": dt.datetime.fromtimestamp(stat.st_mtime),
            }
        )
        return files

    base_path = path_obj
    for child in sorted(base_path.rglob("*")):
        if not child.is_file():
            continue
        stat = child.stat()
        files.append(
            {
                "path": str(child),
                "relative_path": child.relative_to(base_path).as_posix(),
                "size": stat.st_size,
                "modified": dt.datetime.fromtimestamp(stat.st_mtime),
            }
        )
    return files


def validate_source_path(source_path: str) -> str:
    if not source_path.strip():
        raise FileNotFoundError("Source path is empty in config.")
    normalized = normalize_local_path(source_path)
    print("Source path check:")
    print(f"  path = {normalized}")
    if not os.path.exists(normalized):
        raise FileNotFoundError(f"Source path not found: {normalized}")
    print(f"  type = {'directory' if os.path.isdir(normalized) else 'file'}")
    return normalized


def validate_destination_path(
    section: configparser.SectionProxy,
    root: str,
) -> str:
    hostname = section.get("webdav_hostname", "")
    webdav_root = section.get("webdav_root", "")
    full_path = f"{hostname.rstrip('/')}/{webdav_root.strip('/')}"
    if root:
        full_path = f"{full_path}/{root.lstrip('/')}"
    print("Destination path check:")
    print(f"  webdav_hostname = {hostname}")
    print(f"  webdav_root = {webdav_root}")
    print(f"  root = {root}")
    print(f"  composed = {full_path}")
    return full_path


def run_connection_test(source_path: str, client: Client, root: str) -> None:
    if not os.path.exists(source_path):
        raise RuntimeError(f"Connection test failed for source: {source_path}")

    plain_source = " Connection test succeeded for source. "
    source_message = f" Connection test succeeded for {highlight_label('source')}. "
    border = "+" + "-" * len(plain_source) + "+"
    print(f"{SUCCESS_COLOR}{border}")
    print(f"|{source_message}|")
    print(f"{border}{RESET_COLOR}")

    try:
        client.list(root, get_info=True)
    except WebDavException as exc:
        raise RuntimeError(f"Connection test failed for destination: {exc}") from exc

    plain_destination = " Connection test succeeded for destination. "
    destination_message = f" Connection test succeeded for {highlight_label('destination')}. "
    border = "+" + "-" * len(plain_destination) + "+"
    print(f"{SUCCESS_COLOR}{border}")
    print(f"|{destination_message}|")
    print(f"{border}{RESET_COLOR}")


def upload_and_verify_file(
    local_path: str,
    dest_client: Client,
    dest_path: str,
) -> int:
    dest_dir = posixpath.dirname(dest_path)
    ensure_dirs(dest_client, dest_dir)
    with tempfile.NamedTemporaryFile(prefix="nextcloud_verify_") as dest_tmp:
        src_hash = sha256_file(local_path)
        src_size = os.path.getsize(local_path)

        dest_client.upload_sync(remote_path=dest_path, local_path=local_path)
        dest_client.download_sync(remote_path=dest_path, local_path=dest_tmp.name)
        dest_hash = sha256_file(dest_tmp.name)
        dest_size = os.path.getsize(dest_tmp.name)

    if src_size != dest_size or src_hash != dest_hash:
        raise RuntimeError(
            "Verification failed after upload: "
            f"{local_path} -> {dest_path} "
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

    source_path = validate_source_path(config["source"].get("path", ""))
    verify_ssl = config.getboolean("settings", "verify_ssl", fallback=True)
    dest_section = config["destination"]
    dest_root = normalize_root(dest_section.get("root", ""))
    transfer_root = build_dated_root(dest_root)
    validate_destination_path(dest_section, transfer_root)
    dest_client = build_client(dest_section, verify_ssl)

    if conn_test:
        try:
            run_connection_test(source_path, dest_client, dest_root)
        except RuntimeError as exc:
            print(exc)
            print(color_text(COLOR_RED, "종료 상태: 실패"))
            return 1
        print(color_text(COLOR_GREEN, "종료 상태: 성공"))
        return 0

    print("Scanning local source...")
    src_entries = get_local_files(source_path)
    print(f"Found {len(src_entries)} local files in source.")

    print("Scanning destination server...")
    ensure_dirs(dest_client, transfer_root)
    dest_entries = list_tree(dest_client, transfer_root)
    dest_map = build_info_map(dest_entries)

    progress = Progress()
    uploaded = 0
    skipped = 0
    failed = 0
    skip_file = str(DEFAULT_SKIP_LOG)

    for entry in src_entries:
        relative_path = entry["relative_path"]
        dest_path = posixpath.join(transfer_root, relative_path) if transfer_root else relative_path
        src_info = (int(entry["size"]), None, entry["modified"])
        dest_info = dest_map.get(normalize_remote_path(dest_path))
        if should_upload(src_info, dest_info):
            progress.total_files += 1
            progress.total_bytes += int(entry["size"])
    print_transfer_summary(progress)

    for entry in src_entries:
        local_path = str(entry["path"])
        relative_path = str(entry["relative_path"])
        dest_path = posixpath.join(transfer_root, relative_path) if transfer_root else relative_path
        src_info = (int(entry["size"]), None, entry["modified"])
        dest_info = dest_map.get(normalize_remote_path(dest_path))
        if should_upload(src_info, dest_info):
            print(f"Uploading {local_path} -> {dest_path}")
            try:
                transferred_size = upload_and_verify_file(local_path, dest_client, dest_path)
            except RuntimeError as exc:
                print(color_text(COLOR_RED, f"FAILED: {exc}"))
                failed += 1
                continue
            uploaded += 1
            progress.completed_files += 1
            progress.completed_bytes += transferred_size
            print_transfer_summary(progress)
        else:
            dst_url = compose_remote_url(dest_section, dest_path)
            append_skip_log(skip_file, local_path, dst_url)
            print(f"Skipping existing file: {local_path} -> {dst_url}")
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
