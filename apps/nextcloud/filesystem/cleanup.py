#!/usr/bin/env python3
"""
Delete old files from a remote Nextcloud directory over WebDAV.

Configuration is loaded from input.conf (INI format).

Usage:
  python3 cleanup.py /path/to/input.conf
  python3 cleanup.py /path/to/input.conf --days 1
  python3 cleanup.py /path/to/input.conf --days 10 --dry-run
  python3 cleanup.py /path/to/input.conf --days 30 --execute
"""

from __future__ import annotations

import configparser
import datetime as dt
import os
import subprocess
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

CandidateInfo = Dict[str, object]


def print_usage() -> None:
    print("Usage:")
    print("  python3 cleanup.py /path/to/input.conf")
    print("  python3 cleanup.py /path/to/input.conf --days 1")
    print("  python3 cleanup.py /path/to/input.conf --days 10 --dry-run")
    print("  python3 cleanup.py /path/to/input.conf --days 30 --execute")
    print("  python3 cleanup.py /path/to/input.conf --conn_test")


def ensure_log_dir() -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def build_log_path(prefix: str) -> str:
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(ensure_log_dir(), f"{prefix}_{timestamp}.log")


def write_log(log_path: str, lines: List[str]) -> None:
    with open(log_path, "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")


def parse_args(argv: List[str]) -> Tuple[str, int, bool, bool]:
    args = list(argv)
    config_path = "input.conf"
    days = 1
    conn_test = False
    execute = False
    explicit_dry_run = False
    positional: List[str] = []

    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--days":
            index += 1
            if index >= len(args):
                raise ValueError("--days requires a positive integer value")
            try:
                days = int(args[index])
            except ValueError as exc:
                raise ValueError("--days requires a positive integer value") from exc
        elif arg == "--conn_test":
            conn_test = True
        elif arg == "--execute":
            execute = True
        elif arg == "--dry-run":
            explicit_dry_run = True
        elif arg in {"-h", "--help"}:
            print_usage()
            raise SystemExit(0)
        else:
            positional.append(arg)
        index += 1

    if explicit_dry_run and execute:
        raise ValueError("--dry-run and --execute cannot be used together")
    if positional:
        config_path = positional[0]
    if len(positional) > 1:
        raise ValueError("Too many positional arguments.")
    if days <= 0:
        raise ValueError("--days requires a positive integer value")
    return config_path, days, conn_test, execute


def find_candidates(
    entries: List[EntryInfo],
    section: configparser.SectionProxy,
    threshold: dt.datetime,
) -> List[CandidateInfo]:
    candidates: List[CandidateInfo] = []
    now = dt.datetime.now()
    for entry in entries:
        path = entry.get("path")
        if not isinstance(path, str):
            continue

        modified_raw = entry.get("modified") if isinstance(entry.get("modified"), str) else None
        modified = parse_time(modified_raw)
        if modified is None or modified >= threshold:
            continue

        size_value = entry.get("size")
        try:
            size = int(size_value) if size_value is not None else 0
        except (TypeError, ValueError):
            size = 0

        candidates.append(
            {
                "path": path,
                "url": compose_remote_url(section, path),
                "modified": modified,
                "size": size,
                "age_days": (now - modified).days,
            }
        )
    candidates.sort(key=lambda item: (item["modified"], item["path"]))
    return candidates


def render_candidate_report(
    label: str,
    root: str,
    days: int,
    threshold: dt.datetime,
    candidates: List[CandidateInfo],
    mode: str,
) -> List[str]:
    total_size = sum(int(item["size"]) for item in candidates)
    lines = [
        f"[{label}]",
        f"  mode: {mode}",
        f"  root: {root or '/'}",
        f"  delete files older than: {days} day(s)",
        f"  threshold_time: {format_time(threshold)}",
        f"  candidate_count: {len(candidates)}",
        f"  candidate_total_size: {total_size} bytes ({format_bytes(total_size)})",
    ]
    if not candidates:
        lines.append("  no files matched the deletion rule.")
        return lines

    lines.append("  delete candidates:")
    for index, item in enumerate(candidates, start=1):
        lines.append(
            f"    {index}. modified={format_time(item['modified'])} "
            f"age_days={item['age_days']} size={item['size']} path={item['path']}"
        )
    return lines


def print_lines(lines: List[str]) -> None:
    for line in lines:
        print(line)


def ask_for_confirmation() -> bool:
    try:
        answer = input("Type 'confirm' to execute deletion for the files listed above: ").strip()
    except EOFError:
        return False
    return answer == "confirm"


def delete_remote_file(section: configparser.SectionProxy, remote_path: str) -> None:
    hostname = section.get("webdav_hostname")
    webdav_root = section.get("webdav_root")
    username = section.get("username")
    password = section.get("password")
    if not hostname or not webdav_root or not username or not password:
        raise RuntimeError("Missing connection details for DELETE.")

    delete_url = compose_remote_url(section, remote_path)
    command = [
        "curl",
        "--fail",
        "-X",
        "DELETE",
        "-u",
        f"{username}:{password}",
        delete_url,
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise RuntimeError(f"Failed to delete {remote_path}: {details}")


def render_execution_summary(deleted: int, failed: int, failures: List[str]) -> List[str]:
    lines = [f"Deletion finished. Deleted={deleted}, Failed={failed}"]
    if failures:
        lines.append("Failure details:")
        lines.extend(failures)
    return lines


def cleanup_section(
    label: str,
    section: configparser.SectionProxy,
    verify_ssl: bool,
    root: str,
    days: int,
    conn_test: bool,
    execute: bool,
) -> int:
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
    threshold = dt.datetime.now() - dt.timedelta(days=days)
    mode = "execute" if execute else "dry-run"
    candidates = find_candidates(entries, section, threshold)
    preview_lines = render_candidate_report(label, root, days, threshold, candidates, mode)
    print_lines(preview_lines)

    preview_log = build_log_path("cleanup_preview")
    write_log(preview_log, preview_lines)
    print(f"Preview log saved: {preview_log}")

    if not candidates:
        return 0
    if not execute:
        print("Dry-run mode. No files were removed. Re-run with --execute to delete.")
        return 0
    if not ask_for_confirmation():
        print("Deletion cancelled. No files were removed.")
        return 0

    deleted = 0
    failed = 0
    failure_lines: List[str] = []
    action_lines: List[str] = []
    for item in candidates:
        remote_path = item["path"]
        print(f"Deleting {remote_path}")
        try:
            delete_remote_file(section, remote_path)
            deleted += 1
            action_lines.append(f"DELETED path={remote_path}")
        except RuntimeError as exc:
            failed += 1
            error_line = f"FAILED path={remote_path} reason={exc}"
            print(exc)
            action_lines.append(error_line)
            failure_lines.append(error_line)

    summary_lines = render_execution_summary(deleted, failed, failure_lines)
    print_lines(summary_lines)

    execute_log = build_log_path("cleanup_execute")
    write_log(execute_log, preview_lines + [""] + action_lines + [""] + summary_lines)
    print(f"Execution log saved: {execute_log}")
    return 0 if failed == 0 else 1


def main() -> int:
    print_usage()
    try:
        config_path, days, conn_test, execute = parse_args(sys.argv[1:])
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
    return cleanup_section("Target", section, verify_ssl, root, days, conn_test, execute)


if __name__ == "__main__":
    raise SystemExit(main())
