#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Telegram Bot daemon — respond to photo requests and forward motion alerts.

This script runs as a long-lived polling daemon alongside the existing
detection_5min.py cron job.

Features:
  - Responds to /photo, /snap, /latest, 사진, 사진 찍어줘, 찍어줘, 캡처 commands
    by sending the most recent image from the motion directory.
  - Optionally restricts access to a whitelist of chat_ids.
  - Uses the same conf_connect_model.conf configuration file as detection_5min.py.

Usage:
  python3 telegram_bot.py [--config PATH] [--test-config]

Systemd:
  See logs/telegram_bot.service for automatic startup configuration.
"""

from __future__ import annotations

import argparse
import configparser
import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APP_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = APP_DIR / "conf_connect_model.conf"
DEFAULT_MOTION_DIR = Path("/var/lib/motion")
DEFAULT_CAPTURE_DIR = Path("/tmp/berepi_telegram_bot")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Telegram long-polling timeout (seconds) — must be > 0
TELEGRAM_POLL_TIMEOUT = 30
# Seconds to wait between retries after an error
RETRY_BASE_DELAY = 5
RETRY_MAX_DELAY = 300

# Keywords that trigger photo reply (case-insensitive substring match)
PHOTO_KEYWORDS: list[str] = [
    "/photo",
    "/snap",
    "/latest",
    "/카메라",
    "사진 찍어줘",
    "사진찍어줘",
    "사진 보내줘",
    "사진보내줘",
    "찍어줘",
    "캡처",
    "사진",
    "photo",
    "snap",
    "latest",
    "camera",
    "명령 찍어",
    "명령 촬영",
]

# Keywords that trigger a live camera capture before replying.
CURRENT_PHOTO_KEYWORDS: list[str] = [
    "/nowphoto",
    "/capture",
    "/livephoto",
    "지금사진",
    "지금 사진",
    "현재사진",
    "현재 사진",
    "실시간사진",
    "실시간 사진",
    "nowphoto",
    "livephoto",
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TelegramBotConfig:
    token: str
    chat_id: str  # default target for motion alerts (unused by bot daemon itself)
    allowed_chat_ids: set[str] = field(default_factory=set)  # empty = allow all
    timeout_seconds: int = 30


@dataclass
class MotionConfig:
    motion_dir: Path
    recursive: bool = False


@dataclass
class CameraCaptureConfig:
    capture_dir: Path
    capture_command: str = ""
    capture_timeout_seconds: int = 20


@dataclass
class BotAppConfig:
    telegram: TelegramBotConfig
    motion: MotionConfig
    camera: CameraCaptureConfig


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def _get_str(section: configparser.SectionProxy, key: str, default: str = "") -> str:
    value = section.get(key, fallback=default)
    return value.strip() if isinstance(value, str) else str(value).strip()


def _get_int(section: configparser.SectionProxy, key: str, default: int) -> int:
    try:
        return section.getint(key, fallback=default)
    except ValueError:
        return default


def _get_bool(section: configparser.SectionProxy, key: str, default: bool) -> bool:
    try:
        return section.getboolean(key, fallback=default)
    except ValueError:
        return default


def load_config(config_path: Path) -> BotAppConfig:
    if not config_path.exists():
        raise FileNotFoundError(f"configuration file not found: {config_path}")

    parser = configparser.ConfigParser()
    parser.read(config_path, encoding="utf-8")

    tg = parser["telegram"] if parser.has_section("telegram") else parser["DEFAULT"]
    mo = parser["motion"] if parser.has_section("motion") else parser["DEFAULT"]
    ca = parser["camera"] if parser.has_section("camera") else None

    token = _get_str(tg, "bot_token") or _get_str(tg, "token")
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

    chat_id = _get_str(tg, "chat_id")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    # bot_allowed_chat_ids: comma-separated list; empty → allow all
    raw_allowed = _get_str(tg, "bot_allowed_chat_ids", "")
    allowed_chat_ids: set[str] = set()
    if raw_allowed:
        allowed_chat_ids = {cid.strip() for cid in raw_allowed.split(",") if cid.strip()}

    timeout_seconds = _get_int(tg, "timeout_seconds", 30)

    motion_dir = Path(_get_str(mo, "motion_dir", str(DEFAULT_MOTION_DIR))).expanduser()
    recursive = _get_bool(mo, "recursive", False)

    capture_dir = DEFAULT_CAPTURE_DIR
    capture_command = ""
    capture_timeout_seconds = 20
    if ca is not None:
        capture_dir = Path(_get_str(ca, "capture_dir", str(DEFAULT_CAPTURE_DIR))).expanduser()
        capture_command = _get_str(ca, "capture_command", "")
        capture_timeout_seconds = _get_int(ca, "capture_timeout_seconds", 20)

    return BotAppConfig(
        telegram=TelegramBotConfig(
            token=token,
            chat_id=chat_id,
            allowed_chat_ids=allowed_chat_ids,
            timeout_seconds=timeout_seconds,
        ),
        motion=MotionConfig(
            motion_dir=motion_dir,
            recursive=recursive,
        ),
        camera=CameraCaptureConfig(
            capture_dir=capture_dir,
            capture_command=capture_command,
            capture_timeout_seconds=capture_timeout_seconds,
        ),
    )


# ---------------------------------------------------------------------------
# Motion image helpers (mirrors detection_5min.py logic)
# ---------------------------------------------------------------------------


def _image_mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime)


def _iter_images(motion_dir: Path, recursive: bool) -> list[Path]:
    if not motion_dir.exists():
        return []
    candidates = motion_dir.rglob("*") if recursive else motion_dir.iterdir()
    return [p for p in candidates if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS]


def get_latest_image(motion_dir: Path, recursive: bool = False) -> Path | None:
    """Return the most recently modified image in motion_dir, or None."""
    images: list[tuple[Path, datetime]] = []
    for path in _iter_images(motion_dir, recursive):
        try:
            images.append((path, _image_mtime(path)))
        except OSError:
            pass
    if not images:
        return None
    images.sort(key=lambda item: item[1], reverse=True)
    return images[0][0]


# ---------------------------------------------------------------------------
# Live camera capture helpers
# ---------------------------------------------------------------------------


def _build_auto_capture_command(output_path: Path) -> list[str] | None:
    """Return a camera capture command for the current host, if one is available."""
    output = str(output_path)
    if shutil.which("rpicam-still"):
        return ["rpicam-still", "-n", "--timeout", "1000", "-o", output]
    if shutil.which("libcamera-still"):
        return ["libcamera-still", "-n", "--timeout", "1000", "-o", output]
    if shutil.which("fswebcam"):
        return ["fswebcam", "-r", "1280x720", "--no-banner", output]
    if shutil.which("imagesnap"):
        return ["imagesnap", output]
    return None


def _build_configured_capture_command(command_template: str, output_path: Path) -> list[str]:
    """Build a configured capture command, replacing {output} with the JPG path."""
    output = str(output_path)
    if "{output}" in command_template:
        command = command_template.format(output=output)
        return shlex.split(command)
    return [*shlex.split(command_template), output]


def capture_current_image(config: CameraCaptureConfig) -> Path:
    """Capture a live camera image and return the written JPG path."""
    config.capture_dir.mkdir(parents=True, exist_ok=True)
    output_path = config.capture_dir / f"telegram_live_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"

    command = (
        _build_configured_capture_command(config.capture_command, output_path)
        if config.capture_command
        else _build_auto_capture_command(output_path)
    )
    if command is None:
        raise RuntimeError(
            "camera capture command not found. Install rpicam-still/libcamera-still/fswebcam "
            "or set [camera] capture_command in conf_connect_model.conf"
        )

    log.info("capturing live camera image: %s", " ".join(shlex.quote(part) for part in command))
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=config.capture_timeout_seconds,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"camera capture failed with exit code {result.returncode}: {detail}")
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(f"camera capture did not create a valid image: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Telegram API helpers
# ---------------------------------------------------------------------------


def _tg_url(token: str, method: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"


def tg_get_updates(token: str, offset: int | None, poll_timeout: int, request_timeout: int) -> list[dict[str, Any]]:
    """Call getUpdates and return the list of update dicts."""
    import requests  # local import to mirror detection_5min.py style

    params: dict[str, Any] = {"timeout": poll_timeout, "allowed_updates": ["message"]}
    if offset is not None:
        params["offset"] = offset

    response = requests.get(
        _tg_url(token, "getUpdates"),
        params=params,
        timeout=poll_timeout + request_timeout,
    )
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"getUpdates not ok: {data}")
    return data.get("result", [])


def tg_send_photo(token: str, chat_id: str | int, image_path: Path, caption: str, timeout: int) -> None:
    """Send a photo to a Telegram chat."""
    import requests

    url = _tg_url(token, "sendPhoto")
    with image_path.open("rb") as photo:
        response = requests.post(
            url,
            data={"chat_id": str(chat_id), "caption": caption},
            files={"photo": photo},
            timeout=timeout,
        )
    response.raise_for_status()


def tg_send_message(token: str, chat_id: str | int, text: str, timeout: int) -> None:
    """Send a text message to a Telegram chat."""
    import requests

    url = _tg_url(token, "sendMessage")
    response = requests.post(
        url,
        data={"chat_id": str(chat_id), "text": text},
        timeout=timeout,
    )
    response.raise_for_status()


# ---------------------------------------------------------------------------
# Command detection
# ---------------------------------------------------------------------------


def is_photo_request(text: str) -> bool:
    """Return True if the message text contains a photo-request keyword."""
    lower = text.strip().lower()
    for kw in PHOTO_KEYWORDS:
        if kw.lower() in lower:
            return True
    return False


def is_current_photo_request(text: str) -> bool:
    """Return True if the message text asks for a live camera capture."""
    lower = text.strip().lower()
    for kw in CURRENT_PHOTO_KEYWORDS:
        if kw.lower() in lower:
            return True
    return False


def is_allowed(chat_id: str | int, allowed_chat_ids: set[str]) -> bool:
    """Return True if the sender is allowed to use the bot."""
    if not allowed_chat_ids:
        return True  # no restriction
    return str(chat_id) in allowed_chat_ids


# ---------------------------------------------------------------------------
# Event handling
# ---------------------------------------------------------------------------


def handle_photo_request(update: dict[str, Any], config: BotAppConfig) -> None:
    """Respond to a photo request update."""
    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    from_user = message.get("from", {})
    username = from_user.get("username") or from_user.get("first_name") or str(chat_id)

    if chat_id is None:
        log.warning("update has no chat.id; skipping")
        return

    if not is_allowed(chat_id, config.telegram.allowed_chat_ids):
        log.info("chat_id %s not in whitelist; ignoring request from %s", chat_id, username)
        try:
            tg_send_message(
                config.telegram.token,
                chat_id,
                "접근이 허용되지 않은 사용자입니다. (Access denied)",
                config.telegram.timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("send access-denied message failed: %s", exc)
        return

    log.info("photo request from %s (chat_id=%s)", username, chat_id)

    latest = get_latest_image(config.motion.motion_dir, config.motion.recursive)
    if latest is None:
        log.info("no images available in %s", config.motion.motion_dir)
        try:
            tg_send_message(
                config.telegram.token,
                chat_id,
                f"현재 {config.motion.motion_dir} 에 저장된 이미지가 없습니다.",
                config.telegram.timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("send no-image message failed: %s", exc)
        return

    captured_at = _image_mtime(latest).strftime("%Y-%m-%d %H:%M:%S")
    caption = "\n".join(
        [
            "📷 최신 카메라 이미지 (요청 응답)",
            f"파일: {latest.name}",
            f"촬영: {captured_at}",
            f"요청자: {username}",
        ]
    )

    try:
        tg_send_photo(
            config.telegram.token,
            chat_id,
            latest,
            caption,
            config.telegram.timeout_seconds,
        )
        log.info("photo sent to chat_id=%s: %s", chat_id, latest.name)
    except Exception as exc:  # noqa: BLE001
        log.error("send photo failed: %s", exc)
        try:
            tg_send_message(
                config.telegram.token,
                chat_id,
                f"사진 전송 중 오류가 발생했습니다: {exc}",
                config.telegram.timeout_seconds,
            )
        except Exception:  # noqa: BLE001
            pass


def handle_current_photo_request(update: dict[str, Any], config: BotAppConfig) -> None:
    """Capture a live camera image and send it to the requester."""
    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    from_user = message.get("from", {})
    username = from_user.get("username") or from_user.get("first_name") or str(chat_id)

    if chat_id is None:
        log.warning("update has no chat.id; skipping")
        return

    if not is_allowed(chat_id, config.telegram.allowed_chat_ids):
        log.info("chat_id %s not in whitelist; ignoring live capture request from %s", chat_id, username)
        try:
            tg_send_message(
                config.telegram.token,
                chat_id,
                "접근이 허용되지 않은 사용자입니다. (Access denied)",
                config.telegram.timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("send access-denied message failed: %s", exc)
        return

    log.info("live capture request from %s (chat_id=%s)", username, chat_id)

    try:
        image_path = capture_current_image(config.camera)
    except Exception as exc:  # noqa: BLE001
        log.error("live capture failed: %s", exc)
        try:
            tg_send_message(
                config.telegram.token,
                chat_id,
                f"현재 카메라 촬영 중 오류가 발생했습니다: {exc}",
                config.telegram.timeout_seconds,
            )
        except Exception:  # noqa: BLE001
            pass
        return

    captured_at = _image_mtime(image_path).strftime("%Y-%m-%d %H:%M:%S")
    caption = "\n".join(
        [
            "📷 실시간 카메라 이미지 (요청 응답)",
            f"파일: {image_path.name}",
            f"촬영: {captured_at}",
            f"요청자: {username}",
        ]
    )

    try:
        tg_send_photo(
            config.telegram.token,
            chat_id,
            image_path,
            caption,
            config.telegram.timeout_seconds,
        )
        log.info("live photo sent to chat_id=%s: %s", chat_id, image_path.name)
    except Exception as exc:  # noqa: BLE001
        log.error("send live photo failed: %s", exc)
        try:
            tg_send_message(
                config.telegram.token,
                chat_id,
                f"실시간 사진 전송 중 오류가 발생했습니다: {exc}",
                config.telegram.timeout_seconds,
            )
        except Exception:  # noqa: BLE001
            pass


def process_update(update: dict[str, Any], config: BotAppConfig) -> None:
    """Route a single Telegram update to the appropriate handler."""
    message = update.get("message", {})
    text = message.get("text", "") or ""

    if not text:
        return  # ignore non-text updates (stickers, etc.)

    if is_current_photo_request(text):
        handle_current_photo_request(update, config)
    elif is_photo_request(text):
        handle_photo_request(update, config)
    else:
        # Unknown command — silently ignore or log
        chat_id = message.get("chat", {}).get("id", "?")
        log.debug("ignoring unknown message from chat_id=%s: %r", chat_id, text[:80])


# ---------------------------------------------------------------------------
# Polling loop
# ---------------------------------------------------------------------------


def polling_loop(config: BotAppConfig) -> None:
    """Run the bot polling loop indefinitely."""
    token = config.telegram.token
    if not token:
        raise ValueError("Telegram bot_token is empty — set it in conf_connect_model.conf or TELEGRAM_BOT_TOKEN env var")

    log.info("Telegram Bot started (polling). Motion dir: %s", config.motion.motion_dir)
    if config.telegram.allowed_chat_ids:
        log.info("Allowed chat_ids: %s", ", ".join(sorted(config.telegram.allowed_chat_ids)))
    else:
        log.info("No chat_id restriction — all users allowed")

    offset: int | None = None
    retry_delay = RETRY_BASE_DELAY

    while True:
        try:
            updates = tg_get_updates(token, offset, TELEGRAM_POLL_TIMEOUT, config.telegram.timeout_seconds)
            retry_delay = RETRY_BASE_DELAY  # reset on success

            for update in updates:
                update_id: int = update.get("update_id", 0)
                try:
                    process_update(update, config)
                except Exception as exc:  # noqa: BLE001
                    log.error("process_update error (update_id=%s): %s", update_id, exc)
                finally:
                    # Always advance offset to avoid reprocessing
                    offset = update_id + 1

        except KeyboardInterrupt:
            log.info("Bot stopped by user (KeyboardInterrupt)")
            break
        except Exception as exc:  # noqa: BLE001
            log.error("polling error: %s — retrying in %ds", exc, retry_delay)
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, RETRY_MAX_DELAY)


# ---------------------------------------------------------------------------
# Test / validation helpers
# ---------------------------------------------------------------------------


def test_config(config_path: Path) -> int:
    """Validate configuration and print a summary. Returns 0 on success."""
    print(f"Loading config from: {config_path}")
    try:
        config = load_config(config_path)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: config load failed: {exc}", file=sys.stderr)
        return 1

    token = config.telegram.token
    print(f"  bot_token    : {'*' * max(0, len(token) - 6) + token[-6:] if token else '(empty)'}")
    print(f"  chat_id      : {config.telegram.chat_id or '(empty)'}")
    print(f"  allowed_ids  : {', '.join(sorted(config.telegram.allowed_chat_ids)) or '(all allowed)'}")
    print(f"  timeout      : {config.telegram.timeout_seconds}s")
    print(f"  motion_dir   : {config.motion.motion_dir}")
    print(f"  recursive    : {config.motion.recursive}")
    print(f"  capture_dir  : {config.camera.capture_dir}")
    print(f"  capture_cmd  : {config.camera.capture_command or '(auto detect)'}")
    print(f"  capture_timeout: {config.camera.capture_timeout_seconds}s")

    if not token:
        print("ERROR: bot_token is empty", file=sys.stderr)
        return 1

    # Try to call getMe
    try:
        import requests

        url = _tg_url(token, "getMe")
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get("ok"):
            bot = data["result"]
            print(f"  Bot name     : @{bot.get('username')} ({bot.get('first_name')})")
            print("  Bot connection: OK ✓")
        else:
            print(f"ERROR: getMe failed: {data}", file=sys.stderr)
            return 1
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Bot connection test failed: {exc}", file=sys.stderr)
        return 1

    latest = get_latest_image(config.motion.motion_dir, config.motion.recursive)
    if latest:
        print(f"  Latest image : {latest} ({_image_mtime(latest).strftime('%Y-%m-%d %H:%M:%S')})")
    else:
        print(f"  Latest image : (none found in {config.motion.motion_dir})")

    print("\nConfiguration OK. Run without --test-config to start the bot.")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Telegram Bot daemon — responds to photo requests with latest motion image.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 telegram_bot.py                        # start polling bot
  python3 telegram_bot.py --test-config          # validate config and exit
  python3 telegram_bot.py --config /path/to/conf # use custom config
        """,
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"path to configuration file (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--test-config",
        action="store_true",
        help="validate configuration and test bot connection, then exit",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="enable DEBUG logging",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.test_config:
        return test_config(args.config)

    try:
        config = load_config(args.config)
    except Exception as exc:  # noqa: BLE001
        log.error("config load failed: %s", exc)
        return 1

    polling_loop(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
