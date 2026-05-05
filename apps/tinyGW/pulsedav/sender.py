from __future__ import annotations

import argparse

from pulsedav import load_settings, run_loop, send_once


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send system status markdown to WebDAV.")
    parser.add_argument("--once", action="store_true", help="Send one report and exit.")
    parser.add_argument("--loop", action="store_true", help="Run continuously using the configured interval.")
    parser.add_argument("--interval-minutes", type=int, help="Override interval for loop mode.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.loop:
        run_loop(args.interval_minutes)
        return 0

    send_once(load_settings())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
