#!/usr/bin/env python3
"""Run Caddy-based PHP server and display information.

This script starts a php-cgi FastCGI backend and a Caddy web server using the
directory containing this file as the document root. Before launching, it prints
the root directory and the installed PHP version. If required binaries are
missing, the script attempts to install them automatically on Debian/Ubuntu
systems using ``apt-get``.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List

def ensure_binary(name: str, packages: List[str]) -> str:
    """Return path to executable, installing packages when missing."""
    path = shutil.which(name)
    if path:
        return path

    apt = shutil.which("apt-get")
    if apt:
        print(f"{name} not found. Installing via apt-get...")
        try:
            subprocess.run([apt, "update"], check=True)
            subprocess.run([apt, "install", "-y", *packages], check=True)
        except subprocess.CalledProcessError as exc:  # pragma: no cover - runtime path
            print(f"Failed to install {name}: {exc}")
            sys.exit(1)
        path = shutil.which(name)
        if path:
            return path

    print(f"{name} is required but not installed. Please install {name} and retry.")
    sys.exit(1)


def main() -> None:
    php_root = Path(__file__).resolve().parent
    print(f"PHP root directory: {php_root}")

    php_bin = ensure_binary("php", ["php"])
    php_version = subprocess.check_output([php_bin, "-v"]).decode().splitlines()[0]
    print(f"PHP version: {php_version}")

    caddy_bin = ensure_binary("caddy", ["caddy"])
    cgi_bin = ensure_binary("php-cgi", ["php-cgi"])

    cgi_proc = subprocess.Popen([cgi_bin, "-b", "127.0.0.1:9000"])

    with tempfile.NamedTemporaryFile("w", delete=False) as cf:
        cf.write(
            f"""
:8000 {{
    root * {php_root}
    php_fastcgi 127.0.0.1:9000
    file_server
}}
"""
        )
        caddyfile = cf.name

    cmd = [caddy_bin, "run", "--config", caddyfile]
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("Caddy server stopped.")
    finally:
        cgi_proc.terminate()
        cgi_proc.wait()
        Path(caddyfile).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
