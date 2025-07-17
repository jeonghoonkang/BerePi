#!/usr/bin/env python3
"""Utility to migrate a PostgreSQL 15 cluster to version 16 using dump/restore."""

import argparse
import os
import subprocess
from pathlib import Path


def run(cmd: str) -> None:
    """Run a shell command and raise if it fails."""
    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True, check=True)


def ensure_binary(binary: Path, package: str) -> None:
    """Ensure the given binary exists and is executable, otherwise install the package."""
    if binary.exists() and os.access(binary, os.X_OK):
        return

    print(f"{binary} not found or not executable. Installing {package}...")
    run("sudo apt-get update")
    run(f"sudo apt-get install -y {package}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upgrade PostgreSQL data from version 15 to 16 using pg_dumpall and psql"
    )
    parser.add_argument(
        "--dump-file",
        default="pg15_dump.sql",
        help="Temporary dump file path",
    )
    parser.add_argument(
        "--user",
        default="postgres",
        help="Database superuser name",
    )
    parser.add_argument(
        "--old-bin-dir",
        default="/usr/lib/postgresql/15/bin",
        help="Path to PostgreSQL 15 binaries",
    )
    parser.add_argument(
        "--new-bin-dir",
        default="/usr/lib/postgresql/16/bin",
        help="Path to PostgreSQL 16 binaries",
    )
    args = parser.parse_args()

    dump_path = Path(args.dump_file).resolve()
    old_dumpall = Path(args.old_bin_dir) / "pg_dumpall"
    new_psql = Path(args.new_bin_dir) / "psql"

    ensure_binary(old_dumpall, "postgresql-15")
    ensure_binary(new_psql, "postgresql-16")

    run(f"sudo -u {args.user} {old_dumpall} > {dump_path}")
    run(f"sudo -u {args.user} {new_psql} -f {dump_path}")
    print("Upgrade finished. All databases are now on PostgreSQL 16.")


if __name__ == "__main__":
    main()
