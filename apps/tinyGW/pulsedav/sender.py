from __future__ import annotations

import argparse
import json
from copy import deepcopy

from pulsedav import default_settings, load_settings, run_loop, save_settings, send_once


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send system status markdown to WebDAV.")
    parser.add_argument("--once", action="store_true", help="Send one report and exit.")
    parser.add_argument("--loop", action="store_true", help="Run continuously using the configured interval.")
    parser.add_argument("--interval-minutes", type=int, help="Override interval for loop mode.")
    parser.add_argument("--show-defaults", action="store_true", help="Print default initial settings as JSON and exit.")
    parser.add_argument("--show-settings", action="store_true", help="Print effective settings as JSON and exit.")
    parser.add_argument("--write-settings", action="store_true", help="Persist CLI-provided settings into settings.json.")
    parser.add_argument("--hostname", help="Full WebDAV hostname, for example https://example.com:22443")
    parser.add_argument("--server", help="WebDAV server host or IP, for example example.com")
    parser.add_argument("--port", type=int, help="WebDAV server port")
    parser.add_argument("--scheme", choices=["http", "https"], help="WebDAV scheme")
    parser.add_argument("--root-dir", help="WebDAV root directory, for example /remote.php/dav/files/username")
    parser.add_argument("--username", help="WebDAV username")
    parser.add_argument("--password", help="WebDAV password")
    parser.add_argument("--ddns-name", help="DDNS name to record in the report")
    parser.add_argument("--ssh-port", help="SSH port to record in the report")
    parser.add_argument("--intro-text", help="Short intro text stored in the markdown report")
    parser.add_argument("--verify-ssl", dest="verify_ssl", action="store_true", help="Enable SSL verification")
    parser.add_argument("--no-verify-ssl", dest="verify_ssl", action="store_false", help="Disable SSL verification")
    parser.set_defaults(verify_ssl=None)
    return parser.parse_args()


def build_hostname(args: argparse.Namespace) -> str | None:
    if args.hostname:
        return args.hostname.strip()
    if not args.server:
        return None
    scheme = args.scheme or "https"
    server = args.server.strip()
    if server.startswith("http://") or server.startswith("https://"):
        return server.rstrip("/")
    if args.port:
        return f"{scheme}://{server}:{args.port}"
    return f"{scheme}://{server}"


def apply_cli_overrides(settings: dict, args: argparse.Namespace) -> dict:
    updated = deepcopy(settings)
    hostname = build_hostname(args)
    if hostname:
        updated["webdav"]["hostname"] = hostname
    if args.root_dir:
        updated["webdav"]["root"] = args.root_dir.strip()
    if args.username:
        updated["webdav"]["username"] = args.username.strip()
    if args.password:
        updated["webdav"]["password"] = args.password
    if args.verify_ssl is not None:
        updated["webdav"]["verify_ssl"] = args.verify_ssl
    if args.ddns_name is not None:
        updated["metadata"]["ddns_name"] = args.ddns_name.strip()
    if args.ssh_port is not None:
        updated["metadata"]["ssh_port"] = args.ssh_port.strip()
    if args.intro_text is not None:
        updated["metadata"]["intro_text"] = args.intro_text.strip()
    if args.interval_minutes is not None:
        updated["schedule"]["interval_minutes"] = int(args.interval_minutes)
    return updated


def print_settings(settings: dict) -> None:
    print(json.dumps(settings, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> int:
    args = parse_args()
    if args.show_defaults:
        print_settings(default_settings())
        return 0

    settings = apply_cli_overrides(load_settings(), args)

    if args.write_settings:
        save_settings(settings)

    if args.show_settings:
        print_settings(settings)
        return 0

    if args.loop:
        run_loop(int(settings["schedule"]["interval_minutes"]))
        return 0

    send_once(settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
