#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shutil
import socket
import subprocess
import sys
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime


DEFAULT_START_PORT = 1
DEFAULT_END_PORT = 65535
DEFAULT_TIMEOUT_SECONDS = 0.2
DEFAULT_MAX_DURATION_SECONDS = 10.0
DEFAULT_WORKERS = 256


@dataclass(frozen=True)
class OpenPort:
    protocol: str
    address: str
    port: int
    process: str = "-"
    pid: str = "-"


@dataclass(frozen=True)
class ScanResult:
    rows: list[OpenPort]
    skipped_count: int = 0
    timed_out: bool = False


def run_command(args: list[str]) -> str | None:
    if not shutil.which(args[0]):
        return None

    try:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if completed.returncode not in (0, 1):
        return None
    return completed.stdout.strip()


def parse_port_from_address(address: str) -> int | None:
    match = re.search(r":(\d+)(?:\s|\Z|\(|->)", address)
    if not match:
        return None
    return int(match.group(1))


def parse_lsof(output: str) -> list[OpenPort]:
    rows: list[OpenPort] = []
    current: dict[str, str] = {}

    def flush() -> None:
        name = current.get("name", "")
        port = parse_port_from_address(name)
        if port is None:
            return
        rows.append(
            OpenPort(
                protocol=current.get("protocol", "TCP").upper(),
                address=name,
                port=port,
                process=current.get("command", "-"),
                pid=current.get("pid", "-"),
            )
        )

    for line in output.splitlines():
        if not line:
            continue
        field, value = line[0], line[1:]
        if field == "p":
            if current:
                flush()
            current = {"pid": value}
        elif field == "c":
            current["command"] = value
        elif field == "P":
            current["protocol"] = value
        elif field == "n":
            current["name"] = value

    if current:
        flush()
    return rows


def listening_ports_from_lsof() -> list[OpenPort]:
    output = run_command(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN", "-FpcPn"])
    return parse_lsof(output) if output else []


def parse_ss_or_netstat(output: str) -> list[OpenPort]:
    rows: list[OpenPort] = []
    for line in output.splitlines():
        if not line or line.startswith(("Netid", "Proto", "Active")):
            continue

        parts = line.split()
        if len(parts) < 4:
            continue

        protocol = parts[0].upper()
        if protocol not in {"TCP", "TCP4", "TCP6", "UDP", "UDP4", "UDP6"}:
            continue

        address = next((part for part in parts if parse_port_from_address(part) is not None), "")
        port = parse_port_from_address(address)
        if port is None:
            continue

        process = "-"
        pid = "-"
        process_match = re.search(r'users:\(\("([^"]+)",pid=(\d+)', line)
        if process_match:
            process, pid = process_match.groups()

        rows.append(OpenPort(protocol=protocol, address=address, port=port, process=process, pid=pid))
    return rows


def listening_ports_from_system() -> list[OpenPort]:
    rows = listening_ports_from_lsof()
    if rows:
        return rows

    output = run_command(["ss", "-ltnp"])
    if output:
        rows = parse_ss_or_netstat(output)
        if rows:
            return rows

    output = run_command(["netstat", "-anv", "-p", "tcp"])
    if output:
        return parse_ss_or_netstat(output)

    return []


def is_tcp_port_open(host: str, port: int, timeout_seconds: float) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout_seconds)
        return sock.connect_ex((host, port)) == 0


def scan_tcp_ports(
    host: str,
    start_port: int,
    end_port: int,
    timeout_seconds: float,
    max_duration_seconds: float,
    workers: int,
) -> ScanResult:
    ports = iter(range(start_port, end_port + 1))
    rows: list[OpenPort] = []
    pending: dict[Future[bool], int] = {}
    submitted_count = 0
    total_count = end_port - start_port + 1
    deadline = time.monotonic() + max_duration_seconds

    def submit_next(executor: ThreadPoolExecutor) -> bool:
        nonlocal submitted_count
        try:
            port = next(ports)
        except StopIteration:
            return False
        future = executor.submit(is_tcp_port_open, host, port, timeout_seconds)
        pending[future] = port
        submitted_count += 1
        return True

    executor = ThreadPoolExecutor(max_workers=workers)
    try:
        for _ in range(min(workers, total_count)):
            submit_next(executor)

        while pending:
            remaining_seconds = deadline - time.monotonic()
            if remaining_seconds <= 0:
                for future in pending:
                    future.cancel()
                skipped_count = total_count - submitted_count + len(pending)
                return ScanResult(sorted(rows, key=lambda row: row.port), skipped_count=skipped_count, timed_out=True)

            done, _ = wait(pending, timeout=min(remaining_seconds, timeout_seconds), return_when=FIRST_COMPLETED)
            if not done:
                continue

            for future in done:
                port = pending.pop(future)
                try:
                    if future.result():
                        rows.append(OpenPort(protocol="TCP", address=host, port=port))
                except OSError:
                    pass

                if time.monotonic() < deadline:
                    submit_next(executor)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    return ScanResult(sorted(rows, key=lambda row: row.port))


def unique_sorted(rows: list[OpenPort]) -> list[OpenPort]:
    seen: set[tuple[str, str, int, str, str]] = set()
    unique_rows: list[OpenPort] = []
    for row in sorted(rows, key=lambda item: (item.port, item.protocol, item.address, item.process, item.pid)):
        key = (row.protocol, row.address, row.port, row.process, row.pid)
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)
    return unique_rows


def print_ports(rows: list[OpenPort]) -> None:
    if not rows:
        print("No open TCP listening ports found.")
        return

    headers = ("PROTO", "PORT", "ADDRESS", "PROCESS", "PID")
    widths = [
        max(len(headers[0]), *(len(row.protocol) for row in rows)),
        max(len(headers[1]), *(len(str(row.port)) for row in rows)),
        max(len(headers[2]), *(len(row.address) for row in rows)),
        max(len(headers[3]), *(len(row.process) for row in rows)),
        max(len(headers[4]), *(len(row.pid) for row in rows)),
    ]

    print(f"Open ports scanned at {datetime.now().astimezone().isoformat(timespec='seconds')}")
    print(
        f"{headers[0]:<{widths[0]}}  {headers[1]:>{widths[1]}}  "
        f"{headers[2]:<{widths[2]}}  {headers[3]:<{widths[3]}}  {headers[4]:>{widths[4]}}"
    )
    print(
        f"{'-' * widths[0]}  {'-' * widths[1]}  "
        f"{'-' * widths[2]}  {'-' * widths[3]}  {'-' * widths[4]}"
    )
    for row in rows:
        print(
            f"{row.protocol:<{widths[0]}}  {row.port:>{widths[1]}}  "
            f"{row.address:<{widths[2]}}  {row.process:<{widths[3]}}  {row.pid:>{widths[4]}}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print open ports on the local system.")
    parser.add_argument("--scan", action="store_true", help="actively scan TCP ports with localhost connect checks")
    parser.add_argument("--host", default="127.0.0.1", help="host to scan when --scan is used")
    parser.add_argument("--start", type=int, default=DEFAULT_START_PORT, help="first TCP port for --scan")
    parser.add_argument("--end", type=int, default=DEFAULT_END_PORT, help="last TCP port for --scan")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="connect timeout in seconds")
    parser.add_argument(
        "--max-duration",
        type=float,
        default=DEFAULT_MAX_DURATION_SECONDS,
        help="maximum scan duration in seconds before skipping the remaining ports",
    )
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="parallel workers for --scan")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.start < 1 or args.end > 65535 or args.start > args.end:
        print("--start and --end must define a valid port range from 1 to 65535.", file=sys.stderr)
        return 2
    if args.timeout <= 0:
        print("--timeout must be greater than 0.", file=sys.stderr)
        return 2
    if args.max_duration <= 0:
        print("--max-duration must be greater than 0.", file=sys.stderr)
        return 2
    if args.workers < 1:
        print("--workers must be greater than 0.", file=sys.stderr)
        return 2

    if args.scan:
        scan_result = scan_tcp_ports(args.host, args.start, args.end, args.timeout, args.max_duration, args.workers)
        rows = scan_result.rows
    else:
        scan_result = ScanResult([])
        rows = listening_ports_from_system()

    print_ports(unique_sorted(rows))
    if scan_result.timed_out:
        print(f"Skipped {scan_result.skipped_count} ports because scan exceeded {args.max_duration:.1f} seconds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
