#!/usr/bin/env python3
"""Utility to migrate a PostgreSQL 15 cluster to version 16 using dump/restore."""

import argparse
import configparser
import os
import subprocess
from pathlib import Path


def run(cmd: str) -> None:
    """Run a shell command and raise if it fails."""
    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True, check=True)


def start_server(pg_ctl: Path, data_dir: Path, user: str) -> None:
    """Start a PostgreSQL server using pg_ctl."""
    run(f"sudo -u {user} {pg_ctl} -D {data_dir} -l {data_dir}/server.log start")


def stop_server(pg_ctl: Path, data_dir: Path, user: str) -> None:
    """Stop a PostgreSQL server using pg_ctl."""
    run(f"sudo -u {user} {pg_ctl} -D {data_dir} stop")


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
        "--config",
        default="upgrade_pg15_to_pg16.ini",
        help="Path to configuration ini file",
    )
    parser.add_argument("--dump-file", default=None, help="Temporary dump file path")
    parser.add_argument("--user", default=None, help="Database superuser name")
    parser.add_argument("--password", default=None, help="Database password")
    parser.add_argument(
        "--old-bin-dir",
        default=None,
        help="Path to PostgreSQL 15 binaries",
    )
    parser.add_argument(
        "--old-data-dir",
        default=None,
        help="Data directory for the PostgreSQL 15 server",
    )
    parser.add_argument(
        "--new-bin-dir",
        default=None,
        help="Path to PostgreSQL 16 binaries",
    )

    args = parser.parse_args()

    defaults = {
        "dump_file": "pg15_dump.sql",
        "user": "postgres",
        "password": "",
        "old_bin_dir": "/usr/lib/postgresql/15/bin",
        "old_data_dir": "/var/lib/postgresql/15/main",
        "new_bin_dir": "/usr/lib/postgresql/16/bin",
    }

    config = configparser.ConfigParser()
    if Path(args.config).exists():
        config.read(args.config)
        if config.has_section("upgrade"):
            section = config["upgrade"]
            defaults.update(
                {k: section.get(k, v) for k, v in defaults.items()}
            )

    args.dump_file = args.dump_file or defaults["dump_file"]
    args.user = args.user or defaults["user"]
    args.password = args.password or defaults["password"]
    args.old_bin_dir = args.old_bin_dir or defaults["old_bin_dir"]
    args.old_data_dir = args.old_data_dir or defaults["old_data_dir"]
    args.new_bin_dir = args.new_bin_dir or defaults["new_bin_dir"]

    os.environ["PGPASSWORD"] = args.password

    dump_path = Path(args.dump_file).resolve()
    old_dumpall = Path(args.old_bin_dir) / "pg_dumpall"
    old_pg_ctl = Path(args.old_bin_dir) / "pg_ctl"
    new_psql = Path(args.new_bin_dir) / "psql"
    old_data_dir = Path(args.old_data_dir)

    ensure_binary(old_dumpall, "postgresql-15")
    ensure_binary(old_pg_ctl, "postgresql-15")
    ensure_binary(new_psql, "postgresql-16")

    try:
        start_server(old_pg_ctl, old_data_dir, args.user)
        run(f"sudo -u {args.user} {old_dumpall} > {dump_path}")
    finally:
        stop_server(old_pg_ctl, old_data_dir, args.user)


    run(f"sudo -u {args.user} {new_psql} -f {dump_path}")
    print("Upgrade finished. All databases are now on PostgreSQL 16.")


if __name__ == "__main__":
    main()
