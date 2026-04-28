#!/usr/bin/env python3
"""Streamlit app that previews clipboard contents and uploads them to Nextcloud."""

from __future__ import annotations

import base64
import configparser
import hashlib
import importlib.util
import json
import os
import posixpath
import re
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode
from urllib.request import urlopen


def ensure_packages(packages: Dict[str, str]) -> None:
    """Install missing runtime packages when possible."""

    missing = [
        package
        for module, package in packages.items()
        if importlib.util.find_spec(module) is None
    ]
    if not missing:
        return

    print("Installing required packages:", ", ".join(missing))
    subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])


ensure_packages(
    {
        "streamlit": "streamlit",
        "webdav3": "webdavclient3",
    }
)

import streamlit as st  # noqa: E402  # pylint: disable=wrong-import-position


CURRENT_DIR = Path(__file__).resolve().parent
FILESYSTEM_DIR = CURRENT_DIR / "filesystem"
RESOURCE_DIR = CURRENT_DIR / "resource"
if str(FILESYSTEM_DIR) not in sys.path:
    sys.path.insert(0, str(FILESYSTEM_DIR))

from common import build_client, compose_browse_url, compose_remote_url, list_tree, load_config, normalize_root  # noqa: E402


APP_TITLE = "Clipboard to Nextcloud"
DEFAULT_CONFIG = CURRENT_DIR / "input.conf"
TITLE_IMAGE_PATH = RESOURCE_DIR / "clipboard_title_icon.png"
CONFIG_HISTORY_PATH = RESOURCE_DIR / "config_path_history.json"
TELEGRAM_STATE_PATH = RESOURCE_DIR / "telegram_state.json"
CONFIG_HISTORY_LIMIT = 10
SUPPORTED_TARGET_SECTIONS = ("target", "destination")
EDITABLE_CONFIG_KEYS = ("webdav_hostname", "webdav_root", "port", "username", "password", "root")
TELEGRAM_CONFIG_KEYS = (
    "enabled",
    "bot_token",
    "allowed_chat_id",
    "trigger_text",
    "poll_interval_seconds",
    "reply_on_success",
)


def sanitize_filename(value: str) -> str:
    """Convert text into a filesystem-safe name fragment."""

    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned.strip("._") or "device"


def detect_device_name() -> str:
    """Return a stable device name for filenames."""

    return sanitize_filename(socket.gethostname())


def run_command(command: List[str], stdin_text: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run a command and capture its output."""

    return subprocess.run(
        command,
        input=stdin_text,
        text=True,
        capture_output=True,
        check=False,
    )


def read_clipboard_payload() -> Dict[str, Any]:
    """Read clipboard text, HTML, image, and file URLs on macOS via Swift."""

    swift_script = r"""
import AppKit
import Foundation

let pasteboard = NSPasteboard.general
var payload: [String: Any] = [
    "change_count": pasteboard.changeCount,
    "types": []
]

func appendType(_ value: String) {
    var types = payload["types"] as? [String] ?? []
    if !types.contains(value) {
        types.append(value)
    }
    payload["types"] = types
}

func setImagePayload(from image: NSImage) {
    guard let tiffRepresentation = image.tiffRepresentation,
          let bitmap = NSBitmapImageRep(data: tiffRepresentation),
          let pngData = bitmap.representation(using: .png, properties: [:]),
          !pngData.isEmpty else {
        return
    }
    payload["image_base64"] = pngData.base64EncodedString()
    payload["image_size"] = [
        "width": Int(image.size.width),
        "height": Int(image.size.height)
    ]
    appendType("image")
}

let pasteboardTypeNames = pasteboard.types?.map { $0.rawValue } ?? []
if !pasteboardTypeNames.isEmpty {
    payload["pasteboard_types"] = pasteboardTypeNames
}

if let items = pasteboard.pasteboardItems, !items.isEmpty {
    payload["item_count"] = items.count
    payload["item_types"] = items.map { item in
        item.types.map { $0.rawValue }
    }

    for item in items {
        if payload["text"] == nil,
           let text = item.string(forType: .string),
           !text.isEmpty {
            payload["text"] = text
            appendType("text")
        }

        if payload["html"] == nil,
           let htmlData = item.data(forType: .html),
           let html = String(data: htmlData, encoding: .utf8),
           !html.isEmpty {
            payload["html"] = html
            appendType("html")
        }
    }

    var fileURLs: [String] = []
    for item in items {
        if let fileURL = item.string(forType: .fileURL), !fileURL.isEmpty {
            fileURLs.append(fileURL)
        }
    }
    if !fileURLs.isEmpty {
        payload["file_urls"] = fileURLs
        appendType("file_urls")
    }

    if payload["image_base64"] == nil {
        let imageTypesToCheck: [NSPasteboard.PasteboardType] = [
            .png,
            .tiff,
            NSPasteboard.PasteboardType("public.png"),
            NSPasteboard.PasteboardType("public.tiff")
        ]
        for item in items {
            for type in imageTypesToCheck {
                if let data = item.data(forType: type),
                   let image = NSImage(data: data) {
                    setImagePayload(from: image)
                    break
                }
            }
            if payload["image_base64"] != nil {
                break
            }
        }
    }
}

if payload["image_base64"] == nil,
   let images = pasteboard.readObjects(forClasses: [NSImage.self], options: nil) as? [NSImage],
   let image = images.first {
    setImagePayload(from: image)
}

if payload["image_base64"] == nil,
   let image = NSImage(pasteboard: pasteboard) {
    setImagePayload(from: image)
}

if payload["text"] == nil,
   let text = pasteboard.string(forType: .string),
   !text.isEmpty {
    payload["text"] = text
    appendType("text")
}

let jsonData = try JSONSerialization.data(withJSONObject: payload, options: [])
FileHandle.standardOutput.write(jsonData)
"""
    result = run_command(["swift", "-"], stdin_text=swift_script)
    if result.returncode == 0 and result.stdout.strip():
        return json.loads(result.stdout)

    fallback_text = ""
    text_result = run_command(["pbpaste"])
    if text_result.returncode == 0:
        fallback_text = text_result.stdout

    payload: Dict[str, Any] = {"change_count": None, "types": []}
    if fallback_text:
        payload["text"] = fallback_text
        payload["types"] = ["text"]
    if result.stderr.strip():
        payload["warning"] = result.stderr.strip()
    return payload


def load_target_section(config_path: str) -> Tuple[Any, str, bool]:
    """Load the target Nextcloud section from config."""

    config = load_config(config_path)
    verify_ssl = config.getboolean("settings", "verify_ssl", fallback=True)

    for section_name in SUPPORTED_TARGET_SECTIONS:
        if section_name in config:
            section = config[section_name]
            root = normalize_root(section.get("root", ""))
            return section, root, verify_ssl

    raise KeyError(
        f"Missing target section. Expected one of: {', '.join(SUPPORTED_TARGET_SECTIONS)}"
    )


def load_file_transfer_target(config_path: str) -> Tuple[Any, str, bool]:
    """Load the file-transfer target and force uploads into the upload subdirectory."""

    config = load_config(config_path)
    verify_ssl = config.getboolean("settings", "verify_ssl", fallback=True)

    if "destination" not in config:
        raise KeyError("Missing file-transfer target. Expected [destination] section.")

    section = config["destination"]
    root = normalize_root(section.get("root", ""))
    if not root:
        raise ValueError("destination.root is required for file transfer.")

    upload_root = posixpath.join(root, "upload")
    return section, upload_root, verify_ssl


def load_destination_root_target(config_path: str) -> Tuple[Any, str, bool]:
    """Load the destination root for server-side file browsing."""

    config = load_config(config_path)
    verify_ssl = config.getboolean("settings", "verify_ssl", fallback=True)

    if "destination" not in config:
        raise KeyError("Missing server file target. Expected [destination] section.")

    section = config["destination"]
    root = normalize_root(section.get("root", ""))
    if not root:
        raise ValueError("destination.root is required for server file browsing.")

    return section, root, verify_ssl


def show_alert_and_stop(message: str) -> None:
    """Show an alert dialog when possible, then stop the current run."""

    if hasattr(st, "dialog"):
        @st.dialog("설정 필요")
        def _dialog() -> None:
            st.error(message)

        _dialog()
    else:
        st.error(message)

    st.stop()


def load_config_parser(config_path: str) -> configparser.ConfigParser:
    """Load the raw config parser for editing."""

    parser = configparser.ConfigParser()
    if os.path.exists(config_path):
        parser.read(config_path)
    return parser


def ensure_config_sections(parser: configparser.ConfigParser) -> None:
    """Create the editable sections when they do not exist."""

    for section_name in ("source", "destination", "settings", "telegram"):
        if not parser.has_section(section_name):
            parser.add_section(section_name)

    if not parser.has_option("settings", "verify_ssl"):
        parser.set("settings", "verify_ssl", "true")
    if not parser.has_option("telegram", "enabled"):
        parser.set("telegram", "enabled", "false")
    if not parser.has_option("telegram", "trigger_text"):
        parser.set("telegram", "trigger_text", "/clipboard")
    if not parser.has_option("telegram", "poll_interval_seconds"):
        parser.set("telegram", "poll_interval_seconds", "5")
    if not parser.has_option("telegram", "reply_on_success"):
        parser.set("telegram", "reply_on_success", "true")


def save_config_parser(config_path: str, parser: configparser.ConfigParser) -> None:
    """Write the edited config back to disk."""

    config_dir = os.path.dirname(config_path)
    if config_dir:
        os.makedirs(config_dir, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as handle:
        parser.write(handle)


def load_config_path_history() -> List[str]:
    """Load the recently used config paths from disk."""

    if not CONFIG_HISTORY_PATH.exists():
        return []

    try:
        history = json.loads(CONFIG_HISTORY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    if not isinstance(history, list):
        return []

    sanitized_history: List[str] = []
    for value in history:
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed and trimmed not in sanitized_history:
                sanitized_history.append(trimmed)

    return sanitized_history[:CONFIG_HISTORY_LIMIT]


def save_config_path_history(paths: List[str]) -> None:
    """Persist the recently used config paths."""

    RESOURCE_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_HISTORY_PATH.write_text(
        json.dumps(paths[:CONFIG_HISTORY_LIMIT], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def remember_config_path(config_path: str) -> List[str]:
    """Promote the current config path to the front of the recent list."""

    normalized_path = config_path.strip()
    if not normalized_path:
        return st.session_state.get("config_path_history", load_config_path_history())

    current_history = st.session_state.get("config_path_history", load_config_path_history())
    updated_history = [normalized_path]
    updated_history.extend(path for path in current_history if path != normalized_path)
    updated_history = updated_history[:CONFIG_HISTORY_LIMIT]

    save_config_path_history(updated_history)
    st.session_state.config_path_history = updated_history
    return updated_history


def load_telegram_state() -> Dict[str, int]:
    """Load persisted Telegram polling offsets."""

    if not TELEGRAM_STATE_PATH.exists():
        return {}

    try:
        state = json.loads(TELEGRAM_STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

    if not isinstance(state, dict):
        return {}

    sanitized: Dict[str, int] = {}
    for key, value in state.items():
        if isinstance(key, str) and isinstance(value, int):
            sanitized[key] = value
    return sanitized


def save_telegram_state(state: Dict[str, int]) -> None:
    """Persist Telegram polling offsets."""

    RESOURCE_DIR.mkdir(parents=True, exist_ok=True)
    TELEGRAM_STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_telegram_state_key(config_path: str, allowed_chat_id: str, trigger_text: str) -> str:
    """Build a stable state key for one Telegram trigger configuration."""

    fingerprint = hashlib.sha256(
        f"{config_path}|{allowed_chat_id}|{trigger_text}".encode("utf-8")
    ).hexdigest()
    return fingerprint


def load_telegram_settings(config_path: str) -> Dict[str, Any]:
    """Load Telegram bot trigger settings from config."""

    config = load_config_parser(config_path)
    ensure_config_sections(config)
    section = config["telegram"]

    enabled = section.get("enabled", "false").strip().lower() in {"1", "true", "yes", "on"}
    bot_token = section.get("bot_token", "").strip()
    allowed_chat_id = section.get("allowed_chat_id", "").strip()
    trigger_text = section.get("trigger_text", "/clipboard").strip() or "/clipboard"
    reply_on_success = section.get("reply_on_success", "true").strip().lower() in {"1", "true", "yes", "on"}
    poll_interval_raw = section.get("poll_interval_seconds", "5").strip()
    try:
        poll_interval_seconds = max(3, min(300, int(poll_interval_raw or "5")))
    except ValueError:
        poll_interval_seconds = 5

    return {
        "enabled": enabled,
        "bot_token": bot_token,
        "allowed_chat_id": allowed_chat_id,
        "trigger_text": trigger_text,
        "reply_on_success": reply_on_success,
        "poll_interval_seconds": poll_interval_seconds,
    }


def telegram_api_call(bot_token: str, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Call the Telegram Bot API and return the decoded JSON payload."""

    encoded = urlencode({key: value for key, value in params.items() if value is not None})
    url = f"https://api.telegram.org/bot{bot_token}/{method}"
    if encoded:
        url = f"{url}?{encoded}"

    with urlopen(url, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if not isinstance(payload, dict) or not payload.get("ok"):
        raise RuntimeError(f"Telegram API call failed: {method}")
    return payload


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> None:
    """Send a plain Telegram bot message."""

    telegram_api_call(
        bot_token,
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
        },
    )


def claim_telegram_trigger(config_path: str, chat_id: str, update_id: int) -> bool:
    """Claim one Telegram update across multiple app instances via Nextcloud."""

    section, root, verify_ssl = load_target_section(config_path)
    client = build_client(section, verify_ssl)
    claim_root = posixpath.join(root, ".telegram_trigger_claims", sanitize_filename(chat_id)) if root else posixpath.join(
        ".telegram_trigger_claims",
        sanitize_filename(chat_id),
    )
    ensure_remote_dir(client, claim_root)

    claim_path = posixpath.join(claim_root, str(update_id))
    claim_url = compose_remote_url(section, claim_path)
    command = [
        "curl",
        "-sS",
        "-o",
        "/dev/null",
        "-w",
        "%{http_code}",
        "-X",
        "MKCOL",
        "-u",
        f"{section.get('username', '')}:{section.get('password', '')}",
        claim_url,
    ]
    if not verify_ssl:
        command.insert(1, "-k")

    result = subprocess.run(command, check=False, capture_output=True, text=True)
    http_code = result.stdout.strip()
    if http_code == "201":
        return True
    if http_code in {"301", "405"}:
        return False

    details = result.stderr.strip() or http_code or "unknown error"
    raise RuntimeError(f"Telegram trigger claim failed for update_id={update_id}: {details}")


def poll_telegram_clipboard_trigger(config_path: str) -> Optional[Dict[str, str]]:
    """Check Telegram updates and upload the clipboard when the trigger message arrives."""

    settings = load_telegram_settings(config_path)
    if not settings["enabled"]:
        return None
    if not settings["bot_token"] or not settings["allowed_chat_id"]:
        raise ValueError("telegram.enabled=true 인 경우 bot_token 과 allowed_chat_id 가 필요합니다.")

    state = load_telegram_state()
    state_key = get_telegram_state_key(
        config_path,
        settings["allowed_chat_id"],
        settings["trigger_text"],
    )
    offset = state.get(state_key, 0)
    updates_payload = telegram_api_call(
        settings["bot_token"],
        "getUpdates",
        {"offset": offset, "timeout": 0},
    )
    updates = updates_payload.get("result", [])
    if not isinstance(updates, list):
        updates = []

    max_update_id = offset
    if updates:
        max_update_id = max(
            int(update.get("update_id", offset))
            for update in updates
            if isinstance(update, dict) and isinstance(update.get("update_id"), int)
        )

    if offset == 0:
        if max_update_id:
            state[state_key] = max_update_id + 1
            save_telegram_state(state)
        return None

    triggered_message: Dict[str, Any] | None = None
    triggered_update_id: int | None = None
    for update in updates:
        if not isinstance(update, dict):
            continue
        update_id = update.get("update_id")
        if not isinstance(update_id, int):
            continue
        message = update.get("message")
        if not isinstance(message, dict):
            continue
        text = str(message.get("text", "")).strip()
        chat = message.get("chat", {})
        chat_id = str(chat.get("id", "")).strip() if isinstance(chat, dict) else ""
        if chat_id != settings["allowed_chat_id"]:
            continue
        if text != settings["trigger_text"]:
            continue
        triggered_message = message
        triggered_update_id = update_id

    if max_update_id:
        state[state_key] = max_update_id + 1
        save_telegram_state(state)

    if not triggered_message or triggered_update_id is None:
        return None

    if not claim_telegram_trigger(
        config_path,
        settings["allowed_chat_id"],
        triggered_update_id,
    ):
        return None

    payload = read_clipboard_payload()
    remote_path, remote_url = upload_markdown(config_path, payload)
    if settings["reply_on_success"]:
        send_telegram_message(
            settings["bot_token"],
            settings["allowed_chat_id"],
            f"Clipboard uploaded\n{remote_path}\n{remote_url}",
        )
    st.session_state.clipboard_payload = payload
    return {
        "remote_path": remote_path,
        "remote_url": remote_url,
        "trigger_text": settings["trigger_text"],
    }


def apply_selected_config_path() -> None:
    """Copy the selected recent path into the editable input."""

    selected_path = st.session_state.get("config_path_selected", "").strip()
    if selected_path:
        st.session_state.config_path_value = selected_path


def set_transfer_mode(mode: str) -> None:
    """Switch the active transfer mode."""

    st.session_state.transfer_mode = mode


def get_preserved_input_value(section_name: str, key: str, current_value: str) -> str:
    """Keep the current config value when the edit field is left blank."""

    submitted_value = st.session_state.get(f"config_{section_name}_{key}", "")
    if isinstance(submitted_value, str):
        trimmed = submitted_value.strip()
        if trimmed:
            return trimmed
    return current_value


def ensure_remote_dir(client: Any, remote_dir: str) -> None:
    """Create the target directory tree on Nextcloud if needed."""

    if not remote_dir:
        return

    current = ""
    for part in remote_dir.strip("/").split("/"):
        current = posixpath.join(current, part) if current else part
        if not client.check(current):
            client.mkdir(current)


def build_date_directory_name(created_at: datetime) -> str:
    """Return the dated directory name used for uploads."""

    return created_at.strftime("%Y-%m%d")


def build_dated_remote_root(root: str, created_at: datetime) -> str:
    """Append the dated directory under the configured remote root."""

    date_dir = build_date_directory_name(created_at)
    return posixpath.join(root, date_dir) if root else date_dir


def build_file_transfer_root(root: str, created_at: datetime) -> str:
    """Return the dated upload root for file-transfer operations."""

    return build_dated_remote_root(root, created_at)


def build_markdown(payload: Dict[str, Any], created_at: datetime, device_name: str) -> str:
    """Build markdown content from clipboard payload."""
    return build_markdown_content(
        payload,
        created_at,
        device_name,
        include_inline_image=False,
    )


def build_markdown_content(
    payload: Dict[str, Any],
    created_at: datetime,
    device_name: str,
    *,
    include_inline_image: bool,
    image_filename: str | None = None,
) -> str:
    """Build markdown content from clipboard payload."""

    has_content = False
    lines: List[str] = [
        "# Clipboard Capture",
        "",
        f"- created_at: {created_at.isoformat(timespec='seconds')}",
        f"- device_name: {device_name}",
        f"- clipboard_types: {', '.join(payload.get('types', [])) or 'unknown'}",
        "",
    ]

    text = payload.get("text")
    if isinstance(text, str) and text:
        has_content = True
        lines.extend(
            [
                "## Text",
                "",
                "```text",
                text.rstrip("\n"),
                "```",
                "",
            ]
        )

    file_urls = payload.get("file_urls")
    if isinstance(file_urls, list) and file_urls:
        has_content = True
        lines.append("## File URLs")
        lines.append("")
        for url in file_urls:
            lines.append(f"- {url}")
        lines.append("")

    html = payload.get("html")
    if isinstance(html, str) and html:
        has_content = True
        lines.extend(
            [
                "## HTML",
                "",
                "```html",
                html.strip(),
                "```",
                "",
            ]
        )

    image_base64 = payload.get("image_base64")
    if isinstance(image_base64, str) and image_base64:
        has_content = True
        image_size = payload.get("image_size")
        size_text = ""
        if isinstance(image_size, dict):
            width = image_size.get("width")
            height = image_size.get("height")
            if isinstance(width, int) and isinstance(height, int):
                size_text = f" ({width}x{height})"

        lines.extend(["## Image", ""])
        if image_filename:
            lines.append(f"- uploaded_file: {image_filename}{size_text}")
        elif include_inline_image:
            lines.append(f'<img alt="clipboard image" src="data:image/png;base64,{image_base64}" />')
        else:
            lines.append(f"[clipboard image omitted from preview{size_text}]")
        lines.append("")

    if not has_content:
        lines.extend(["클립보드에서 표시 가능한 텍스트/이미지 데이터를 찾지 못했습니다.", ""])

    return "\n".join(lines)


def upload_markdown(config_path: str, payload: Dict[str, Any]) -> Tuple[str, str]:
    """Upload a generated markdown file to Nextcloud and return path/url."""

    section, root, verify_ssl = load_target_section(config_path)
    client = build_client(section, verify_ssl)

    created_at = datetime.now().astimezone()
    dated_root = build_dated_remote_root(root, created_at)
    ensure_remote_dir(client, dated_root)
    device_name = detect_device_name()
    timestamp = created_at.strftime('%Y%m%d_%H%M%S')
    markdown_filename = f"{timestamp}_{device_name}_clipboard.md"
    remote_path = posixpath.join(dated_root, markdown_filename) if dated_root else markdown_filename

    text = payload.get("text")
    file_urls = payload.get("file_urls")
    html = payload.get("html")
    image_base64 = payload.get("image_base64")
    image_only = (
        isinstance(image_base64, str)
        and bool(image_base64)
        and not (isinstance(text, str) and text.strip())
        and not (isinstance(file_urls, list) and bool(file_urls))
        and not (isinstance(html, str) and html.strip())
    )

    image_filename: str | None = None
    image_temp_path: str | None = None
    if isinstance(image_base64, str) and image_base64:
        image_prefix = "image_" if image_only else ""
        image_filename = f"{image_prefix}{timestamp}_{device_name}_clipboard.png"
        image_remote_path = posixpath.join(dated_root, image_filename) if dated_root else image_filename
        try:
            image_bytes = base64.b64decode(image_base64)
            with tempfile.NamedTemporaryFile(
                mode="wb",
                suffix=".png",
                prefix="clipboard_image_",
                delete=False,
            ) as handle:
                handle.write(image_bytes)
                image_temp_path = handle.name
            client.upload_sync(remote_path=image_remote_path, local_path=image_temp_path)
        finally:
            if image_temp_path and os.path.exists(image_temp_path):
                os.unlink(image_temp_path)

        if image_only:
            return image_remote_path, compose_browse_url(section, image_remote_path)

    markdown = build_markdown_content(
        payload,
        created_at,
        device_name,
        include_inline_image=False,
        image_filename=image_filename,
    )

    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".md",
            prefix="clipboard_",
            delete=False,
            encoding="utf-8",
        ) as handle:
            handle.write(markdown)
            temp_path = handle.name
        client.upload_sync(remote_path=remote_path, local_path=temp_path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

    return remote_path, compose_browse_url(section, remote_path)


def upload_selected_file(config_path: str, filename: str, file_bytes: bytes) -> Tuple[str, str]:
    """Upload a user-selected file to Nextcloud and return path/url."""

    section, root, verify_ssl = load_file_transfer_target(config_path)
    client = build_client(section, verify_ssl)
    created_at = datetime.now().astimezone()
    dated_root = build_file_transfer_root(root, created_at)
    ensure_remote_dir(client, dated_root)

    remote_name = Path(filename).name or "uploaded_file"
    remote_path = posixpath.join(dated_root, remote_name) if dated_root else remote_name

    temp_path: str | None = None
    try:
        suffix = Path(remote_name).suffix
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=suffix,
            prefix="selected_file_",
            delete=False,
        ) as handle:
            handle.write(file_bytes)
            temp_path = handle.name
        client.upload_sync(remote_path=remote_path, local_path=temp_path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

    return remote_path, compose_browse_url(section, remote_path)


def compose_directory_browse_url(config_path: str, remote_dir: str) -> str:
    """Build a directory browse URL in the Nextcloud web UI."""

    section, _, _ = load_file_transfer_target(config_path)
    normalized_dir = normalize_root(remote_dir)
    if not normalized_dir:
        return compose_browse_url(section, "")

    parent_dir, name = posixpath.split(normalized_dir)
    browse_target = posixpath.join(parent_dir, name) if parent_dir else name
    return f"{section.get('webdav_hostname', '').rstrip('/')}/index.php/apps/files/?dir=/{browse_target}"


def scan_local_directory(local_dir: str) -> Dict[str, Any]:
    """Scan a local directory and collect upload metadata."""

    directory = Path(local_dir).expanduser().resolve()
    if not directory.exists():
        raise FileNotFoundError(f"Local directory not found: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"Local path is not a directory: {directory}")

    dir_count = 0
    file_count = 0
    total_bytes = 0
    sample_entries: List[str] = []

    for current_root, dirnames, filenames in os.walk(directory):
        current_dir = Path(current_root)
        relative_dir = current_dir.relative_to(directory)
        dir_count += len(dirnames)

        for filename in sorted(filenames):
            file_path = current_dir / filename
            relative_path = (relative_dir / filename).as_posix() if relative_dir != Path(".") else filename
            total_bytes += file_path.stat().st_size
            file_count += 1
            if len(sample_entries) < 10:
                sample_entries.append(relative_path)

    return {
        "directory": str(directory),
        "name": directory.name or directory.as_posix(),
        "dir_count": dir_count,
        "file_count": file_count,
        "total_bytes": total_bytes,
        "sample_entries": sample_entries,
    }


def upload_directory_tree(config_path: str, local_dir: str) -> Tuple[str, str, int, int]:
    """Upload a local directory tree into the forced file-transfer root."""

    section, root, verify_ssl = load_file_transfer_target(config_path)
    client = build_client(section, verify_ssl)
    source_dir = Path(local_dir).expanduser().resolve()
    if not source_dir.is_dir():
        raise NotADirectoryError(f"Local path is not a directory: {source_dir}")

    created_at = datetime.now().astimezone()
    dated_root = build_file_transfer_root(root, created_at)
    remote_base_dir = posixpath.join(dated_root, source_dir.name) if dated_root else source_dir.name
    ensure_remote_dir(client, remote_base_dir)

    uploaded_dir_count = 0
    uploaded_file_count = 0

    for current_root, dirnames, filenames in os.walk(source_dir):
        current_dir = Path(current_root)
        relative_dir = current_dir.relative_to(source_dir)
        remote_current_dir = (
            posixpath.join(remote_base_dir, relative_dir.as_posix())
            if relative_dir != Path(".")
            else remote_base_dir
        )
        ensure_remote_dir(client, remote_current_dir)

        for dirname in sorted(dirnames):
            child_dir = posixpath.join(remote_current_dir, dirname)
            ensure_remote_dir(client, child_dir)
            uploaded_dir_count += 1

        for filename in sorted(filenames):
            local_file_path = current_dir / filename
            remote_file_path = posixpath.join(remote_current_dir, filename)
            client.upload_sync(remote_path=remote_file_path, local_path=str(local_file_path))
            uploaded_file_count += 1

    return (
        remote_base_dir,
        compose_directory_browse_url(config_path, remote_base_dir),
        uploaded_dir_count,
        uploaded_file_count,
    )


def reset_transfer_confirmation(confirm_key: str) -> None:
    """Clear a stale confirmation marker for a transfer target."""

    st.session_state[confirm_key] = False


def bytes_to_text(size: int) -> str:
    """Format a byte count for display."""

    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    unit_index = 0
    while value >= 1024 and unit_index < len(units) - 1:
        value /= 1024.0
        unit_index += 1
    return f"{value:.1f} {units[unit_index]}"


def list_server_files(config_path: str) -> Tuple[Any, str, List[str]]:
    """List files under destination.root for server-side browsing."""

    section, root, verify_ssl = load_destination_root_target(config_path)
    client = build_client(section, verify_ssl)
    entries = list_tree(client, root)
    file_paths = sorted(
        path
        for entry in entries
        if isinstance((path := entry.get("path")), str)
    )
    return section, root, file_paths


def fetch_server_file_preview(config_path: str, remote_path: str) -> Dict[str, Any]:
    """Download a remote file and prepare a preview payload."""

    section, _, verify_ssl = load_destination_root_target(config_path)
    client = build_client(section, verify_ssl)
    suffix = Path(remote_path).suffix
    temp_path: str | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=suffix,
            prefix="server_file_preview_",
            delete=False,
        ) as handle:
            temp_path = handle.name
        client.download_sync(remote_path=remote_path, local_path=temp_path)
        data = Path(temp_path).read_bytes()
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

    preview: Dict[str, Any] = {
        "path": remote_path,
        "size": len(data),
        "suffix": suffix.lower(),
        "browse_url": compose_browse_url(section, remote_path),
    }

    lower_suffix = suffix.lower()
    if lower_suffix in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}:
        preview["kind"] = "image"
        preview["bytes"] = data
        return preview

    if lower_suffix in {".md", ".txt", ".json", ".py", ".yaml", ".yml", ".csv", ".log", ".ini", ".conf", ".html"}:
        preview["kind"] = "text"
        preview["text"] = data.decode("utf-8", errors="replace")
        return preview

    preview["kind"] = "binary"
    preview["text"] = data[:512].hex(" ")
    return preview


def delete_server_files(config_path: str, remote_paths: List[str]) -> int:
    """Delete selected files from destination.root."""

    section, _, verify_ssl = load_destination_root_target(config_path)
    client = build_client(section, verify_ssl)
    deleted = 0
    for remote_path in remote_paths:
        if not remote_path:
            continue
        delete_url = compose_remote_url(section, remote_path)
        command = [
            "curl",
            "--fail",
            "-X",
            "DELETE",
            "-u",
            f"{section.get('username', '')}:{section.get('password', '')}",
            delete_url,
        ]
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            details = result.stderr.strip() or result.stdout.strip() or "unknown error"
            raise RuntimeError(f"Failed to delete {remote_path}: {details}")
        deleted += 1
    return deleted


def sync_server_file_selection(file_paths: List[str]) -> None:
    """Keep the selected server file index within the current file list."""

    if "server_file_index" not in st.session_state:
        st.session_state.server_file_index = 0
    if not file_paths:
        st.session_state.server_file_index = 0
        st.session_state.server_file_selected = ""
        return

    current_selected = st.session_state.get("server_file_selected", "")
    if current_selected in file_paths:
        st.session_state.server_file_index = file_paths.index(current_selected)
    else:
        st.session_state.server_file_index = min(st.session_state.server_file_index, len(file_paths) - 1)
        st.session_state.server_file_selected = file_paths[st.session_state.server_file_index]


def apply_server_file_selection() -> None:
    """Update the current server file index from the selectbox choice."""

    selected = st.session_state.get("server_file_selected", "")
    file_paths = st.session_state.get("server_file_paths", [])
    if selected in file_paths:
        st.session_state.server_file_index = file_paths.index(selected)
    st.session_state.server_file_single_delete_confirmed = False


def move_server_file(step: int) -> None:
    """Move the current server file selection forward or backward."""

    file_paths = st.session_state.get("server_file_paths", [])
    if not file_paths:
        return
    current_index = st.session_state.get("server_file_index", 0)
    next_index = max(0, min(len(file_paths) - 1, current_index + step))
    st.session_state.server_file_index = next_index
    st.session_state.server_file_selected = file_paths[next_index]
    st.session_state.server_file_single_delete_confirmed = False


def render_clipboard_preview(payload: Dict[str, Any]) -> None:
    """Render clipboard contents in the Streamlit UI."""

    types = payload.get("types") or []
    st.caption(f"감지된 타입: {', '.join(types) if types else '없음'}")
    pasteboard_types = payload.get("pasteboard_types")
    if isinstance(pasteboard_types, list) and pasteboard_types:
        st.caption(f"raw pasteboard types: {', '.join(str(value) for value in pasteboard_types)}")

    warning = payload.get("warning")
    if isinstance(warning, str) and warning:
        st.warning(warning)

    text = payload.get("text")
    if isinstance(text, str) and text:
        st.subheader("텍스트")
        st.text_area("clipboard_text", text, height=220, label_visibility="collapsed")

    file_urls = payload.get("file_urls")
    if isinstance(file_urls, list) and file_urls:
        st.subheader("파일 URL")
        st.code("\n".join(str(url) for url in file_urls), language="text")

    html = payload.get("html")
    if isinstance(html, str) and html:
        with st.expander("HTML 보기"):
            st.code(html, language="html")

    image_base64 = payload.get("image_base64")
    if isinstance(image_base64, str) and image_base64:
        st.subheader("이미지")
        image_size = payload.get("image_size")
        if isinstance(image_size, dict):
            width = image_size.get("width")
            height = image_size.get("height")
            if isinstance(width, int) and isinstance(height, int):
                st.caption(f"image size: {width}x{height}")
        st.image(base64.b64decode(image_base64), caption="Clipboard image preview")

    if not any(
        [
            isinstance(text, str) and bool(text),
            isinstance(file_urls, list) and bool(file_urls),
            isinstance(html, str) and bool(html),
            isinstance(image_base64, str) and bool(image_base64),
        ]
    ):
        st.info("클립보드에 표시 가능한 텍스트, 파일 URL, 이미지가 없습니다.")


def render_telegram_trigger_status_button() -> None:
    """Render a button-like status indicator for recent Telegram triggers."""

    highlight_until = float(st.session_state.get("telegram_trigger_highlight_until", 0.0) or 0.0)
    is_triggered = time.time() < highlight_until
    last_result = st.session_state.get("telegram_last_trigger_result")

    label = "Telegram 대기중"
    detail = "트리거를 기다리는 중입니다."
    background = "#94a3b8"
    border = "#64748b"

    if is_triggered:
        label = "Telegram Trigger 감지됨"
        detail = "클립보드 자동 전송이 방금 실행되었습니다."
        background = "#dc2626"
        border = "#991b1b"
    elif isinstance(last_result, dict) and last_result.get("remote_path"):
        label = "Telegram Trigger 처리완료"
        detail = str(last_result.get("remote_path"))
        background = "#16a34a"
        border = "#166534"

    st.markdown(
        f"""
        <div style="margin: 0.5rem 0 1rem 0;">
          <div style="
              width: 100%;
              border-radius: 0.6rem;
              border: 1px solid {border};
              background: {background};
              color: white;
              padding: 0.85rem 1rem;
              text-align: center;
              font-weight: 700;
              box-shadow: 0 2px 8px rgba(15, 23, 42, 0.15);
          ">
            {label}
          </div>
          <div style="font-size: 0.85rem; color: #475569; margin-top: 0.35rem;">
            {detail}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    """Render the Streamlit app."""

    st.set_page_config(page_title=APP_TITLE, page_icon="📋", layout="wide")

    if "config_path_history" not in st.session_state:
        st.session_state.config_path_history = load_config_path_history()
    if "config_path_value" not in st.session_state:
        history = st.session_state.config_path_history
        st.session_state.config_path_value = history[0] if history else str(DEFAULT_CONFIG)
    if "transfer_mode" not in st.session_state:
        st.session_state.transfer_mode = "clipboard"
    if "file_transfer_confirmed_file" not in st.session_state:
        st.session_state.file_transfer_confirmed_file = ""
    if "file_transfer_confirmed_dir" not in st.session_state:
        st.session_state.file_transfer_confirmed_dir = ""
    if "file_uploader_nonce" not in st.session_state:
        st.session_state.file_uploader_nonce = 0
    if "directory_transfer_path" not in st.session_state:
        st.session_state.directory_transfer_path = ""
    if "server_file_delete_confirmed" not in st.session_state:
        st.session_state.server_file_delete_confirmed = False
    if "server_file_single_delete_confirmed" not in st.session_state:
        st.session_state.server_file_single_delete_confirmed = False
    if "telegram_last_trigger_result" not in st.session_state:
        st.session_state.telegram_last_trigger_result = None
    if "telegram_trigger_highlight_until" not in st.session_state:
        st.session_state.telegram_trigger_highlight_until = 0.0
    history = st.session_state.config_path_history
    st.session_state.config_path_selected = (
        st.session_state.config_path_value
        if st.session_state.config_path_value in history
        else (history[0] if history else "")
    )

    #st.write("Copy Machine BerePi")
    title_icon_col, title_text_col = st.columns([0.12, 0.88])
    with title_icon_col:
        if TITLE_IMAGE_PATH.exists():
            st.image(str(TITLE_IMAGE_PATH), width=72)
    with title_text_col:
        st.markdown(
            "<h1 style='font-size: 16px; margin: 0;'>Clipboard to Nextcloud</h1>",
            unsafe_allow_html=True,
        )
    st.write("현재 macOS 클립보드를 미리 보고, Nextcloud 대상 디렉토리에 Markdown 파일로 업로드합니다.")

    mode_col1, mode_col2, mode_col3, _ = st.columns([1, 1, 1, 5])
    with mode_col1:
        st.button(
            "클립보드",
            type="primary" if st.session_state.transfer_mode == "clipboard" else "secondary",
            use_container_width=True,
            on_click=set_transfer_mode,
            args=("clipboard",),
        )
    with mode_col2:
        st.button(
            "파일전송",
            type="primary" if st.session_state.transfer_mode == "file" else "secondary",
            use_container_width=True,
            on_click=set_transfer_mode,
            args=("file",),
        )
    with mode_col3:
        st.button(
            "서버파일",
            type="primary" if st.session_state.transfer_mode == "server_files" else "secondary",
            use_container_width=True,
            on_click=set_transfer_mode,
            args=("server_files",),
        )

    if "clipboard_payload" not in st.session_state:
        st.session_state.clipboard_payload = read_clipboard_payload()

    target_root_display = "/"
    file_transfer_root_display = "/upload"

    with st.sidebar:
        st.header("설정")
        history = st.session_state.config_path_history
        if history:
            st.selectbox(
                "Recent config paths",
                options=[""] + history,
                format_func=lambda value: value if value else "직접 입력",
                key="config_path_selected",
                on_change=apply_selected_config_path,
            )
        config_path = st.text_input("Config path", key="config_path_value")
        st.caption("최근 사용 경로는 최대 10개까지 저장됩니다. `[target]` 또는 `[destination]` 섹션을 사용합니다.")

        try:
            editor_parser = load_config_parser(config_path)
            ensure_config_sections(editor_parser)
        except Exception as exc:  # pragma: no cover - UI error path
            st.error(f"설정 파일 로드 실패: {exc}")
            editor_parser = None

        if editor_parser is not None:
            with st.expander("Config 편집", expanded=False):
                with st.form("config_editor_form"):
                    for section_name in ("source", "destination"):
                        st.markdown(f"**[{section_name}]**")
                        for key in EDITABLE_CONFIG_KEYS:
                            current_value = editor_parser.get(section_name, key, fallback="")
                            is_secret = key == "password"
                            session_key = f"config_{section_name}_{key}"
                            if session_key not in st.session_state:
                                st.session_state[session_key] = ""
                            st.text_input(
                                f"{section_name}.{key}",
                                value=st.session_state[session_key],
                                placeholder=current_value,
                                type="password" if is_secret else "default",
                                key=session_key,
                            )

                    verify_ssl_default = editor_parser.getboolean(
                        "settings",
                        "verify_ssl",
                        fallback=True,
                    )
                    st.checkbox(
                        "settings.verify_ssl",
                        value=verify_ssl_default,
                        key="config_settings_verify_ssl",
                    )

                    st.markdown("**[telegram]**")
                    for key in ("bot_token", "allowed_chat_id", "trigger_text", "poll_interval_seconds"):
                        current_value = editor_parser.get("telegram", key, fallback="")
                        session_key = f"config_telegram_{key}"
                        if session_key not in st.session_state:
                            st.session_state[session_key] = ""
                        st.text_input(
                            f"telegram.{key}",
                            value=st.session_state[session_key],
                            placeholder=current_value,
                            type="password" if key == "bot_token" else "default",
                            key=session_key,
                        )
                    st.checkbox(
                        "telegram.enabled",
                        value=editor_parser.getboolean("telegram", "enabled", fallback=False),
                        key="config_telegram_enabled",
                    )
                    st.checkbox(
                        "telegram.reply_on_success",
                        value=editor_parser.getboolean("telegram", "reply_on_success", fallback=True),
                        key="config_telegram_reply_on_success",
                    )

                    save_clicked = st.form_submit_button("설정 파일 저장", use_container_width=True)

                if save_clicked:
                    try:
                        for section_name in ("source", "destination"):
                            for key in EDITABLE_CONFIG_KEYS:
                                editor_parser.set(
                                    section_name,
                                    key,
                                    get_preserved_input_value(
                                        section_name,
                                        key,
                                        editor_parser.get(section_name, key, fallback=""),
                                    ),
                                )
                        editor_parser.set(
                            "settings",
                            "verify_ssl",
                            "true" if st.session_state.get("config_settings_verify_ssl", True) else "false",
                        )
                        for key in ("bot_token", "allowed_chat_id", "trigger_text", "poll_interval_seconds"):
                            editor_parser.set(
                                "telegram",
                                key,
                                get_preserved_input_value(
                                    "telegram",
                                    key,
                                    editor_parser.get("telegram", key, fallback=""),
                                ),
                            )
                        editor_parser.set(
                            "telegram",
                            "enabled",
                            "true" if st.session_state.get("config_telegram_enabled", False) else "false",
                        )
                        editor_parser.set(
                            "telegram",
                            "reply_on_success",
                            "true" if st.session_state.get("config_telegram_reply_on_success", True) else "false",
                        )
                        save_config_parser(config_path, editor_parser)
                    except Exception as exc:  # pragma: no cover - UI error path
                        st.error(f"설정 저장 실패: {exc}")
                    else:
                        remember_config_path(config_path)
                        st.success(f"설정 저장 완료: {config_path}")
                        st.rerun()

        try:
            section, root, verify_ssl = load_target_section(config_path)
            remember_config_path(config_path)
            target_root_display = root or "/"
            st.success("Nextcloud 설정을 읽었습니다.")
            st.code(
                "\n".join(
                    [
                        f"hostname: {section.get('webdav_hostname', '')}",
                        f"root: {root or '/'}",
                        f"verify_ssl: {verify_ssl}",
                    ]
                ),
                language="text",
            )
        except Exception as exc:  # pragma: no cover - UI error path
            st.error(f"설정 확인 실패: {exc}")

        file_transfer_error: str | None = None
        try:
            _, file_transfer_root, _ = load_file_transfer_target(config_path)
            file_transfer_root_display = build_file_transfer_root(
                file_transfer_root,
                datetime.now().astimezone(),
            ) or "/upload"
        except Exception as exc:
            file_transfer_root_display = "/upload"
            file_transfer_error = str(exc)

        if st.session_state.transfer_mode == "clipboard" and st.button("클립보드 새로고침", use_container_width=True):
            with st.spinner("클립보드 읽는 중..."):
                st.session_state.clipboard_payload = read_clipboard_payload()
            st.rerun()

        try:
            telegram_settings = load_telegram_settings(config_path)
        except Exception as exc:  # pragma: no cover - UI error path
            telegram_settings = None
            st.error(f"Telegram 설정 확인 실패: {exc}")
        else:
            if telegram_settings["enabled"]:
                st.info(
                    "Telegram 자동 전송 감시 활성화: "
                    f"chat_id={telegram_settings['allowed_chat_id'] or '-'}, "
                    f"trigger={telegram_settings['trigger_text']}, "
                    f"poll={telegram_settings['poll_interval_seconds']}s"
                )

    payload = st.session_state.clipboard_payload

    telegram_settings_runtime: Optional[Dict[str, Any]]
    try:
        telegram_settings_runtime = load_telegram_settings(config_path)
    except Exception:
        telegram_settings_runtime = None
    if telegram_settings_runtime and telegram_settings_runtime["enabled"]:
        try:
            trigger_result = poll_telegram_clipboard_trigger(config_path)
        except Exception as exc:  # pragma: no cover - UI error path
            st.error(f"Telegram 트리거 처리 실패: {exc}")
            trigger_result = None
        if trigger_result:
            st.session_state.telegram_last_trigger_result = trigger_result
            st.session_state.telegram_trigger_highlight_until = time.time() + 30
            st.success(
                "Telegram 트리거로 클립보드 전송 완료: "
                f"{trigger_result['remote_path']}"
            )
            st.markdown(f"[원격 URL 열기]({trigger_result['remote_url']})")

    if st.session_state.transfer_mode == "file" and file_transfer_error:
        show_alert_and_stop(
            "파일전송을 사용하려면 설정 파일의 [destination] 섹션에 root 값을 입력해 주세요."
        )
    if st.session_state.transfer_mode == "server_files":
        try:
            _, destination_root_display, server_file_paths = list_server_files(config_path)
            st.session_state.server_file_paths = server_file_paths
            sync_server_file_selection(server_file_paths)
        except Exception:
            show_alert_and_stop(
                "서버파일을 사용하려면 설정 파일의 [destination] 섹션에 root 값을 입력해 주세요."
            )

    if st.session_state.transfer_mode == "clipboard":
        left_col, right_col = st.columns([1.2, 0.8])

        with left_col:
            st.subheader("클립보드 미리보기")
            render_clipboard_preview(payload)

        with right_col:
            st.subheader("업로드")
            if telegram_settings_runtime and telegram_settings_runtime["enabled"]:
                render_telegram_trigger_status_button()
            created_at = datetime.now().astimezone()
            device_name = detect_device_name()
            markdown_preview = build_markdown_content(
                payload,
                created_at,
                device_name,
                include_inline_image=False,
                image_filename="[will upload as .png file]",
            )
            st.code(markdown_preview, language="markdown")

            if st.button("전송", type="primary", use_container_width=True):
                try:
                    remote_path, remote_url = upload_markdown(config_path, payload)
                except Exception as exc:  # pragma: no cover - UI error path
                    st.exception(exc)
                else:
                    st.success(f"업로드 완료: {remote_path}")
                    st.markdown(f"[원격 URL 열기]({remote_url})")
    elif st.session_state.transfer_mode == "file":
        left_col, right_col = st.columns([1.1, 0.9])

        directory_scan: Dict[str, Any] | None = None
        directory_scan_error: str | None = None

        with left_col:
            st.subheader("파일 선택")
            uploaded_files = st.file_uploader(
                "업로드할 파일",
                accept_multiple_files=True,
                label_visibility="collapsed",
                key=f"file_transfer_uploads_{st.session_state.file_uploader_nonce}",
            ) or []
            too_many_files = len(uploaded_files) > 10
            selected_files = uploaded_files[:10]
            if too_many_files:
                st.error("파일은 한 번에 최대 10개까지 선택할 수 있습니다.")

            if selected_files:
                total_selected_size = sum(file.size for file in selected_files)
                st.write(f"선택 파일 수: {len(selected_files)}")
                st.write(f"총 크기: {bytes_to_text(total_selected_size)}")
                for index, uploaded_file in enumerate(selected_files, start=1):
                    st.write(f"{index}. {uploaded_file.name} ({uploaded_file.size:,} bytes)")
                    if uploaded_file.type:
                        st.caption(f"MIME: {uploaded_file.type}")
                if len(selected_files) == 1:
                    uploaded_file = selected_files[0]
                    if uploaded_file.type and uploaded_file.type.startswith("image/"):
                        st.image(uploaded_file, caption=uploaded_file.name)
            else:
                st.info("전송할 파일을 최대 10개까지 선택해 주세요.")

            st.divider()
            st.subheader("디렉토리 스캔")
            directory_path = st.text_input(
                "로컬 디렉토리 경로",
                key="directory_transfer_path",
                placeholder="/Users/tinyos/Downloads/sample_dir",
            ).strip()
            if directory_path:
                try:
                    directory_scan = scan_local_directory(directory_path)
                except Exception as exc:  # pragma: no cover - UI error path
                    directory_scan_error = str(exc)
                    st.error(f"디렉토리 스캔 실패: {exc}")
                else:
                    st.write(f"디렉토리: {directory_scan['directory']}")
                    st.write(f"하위 디렉토리 수: {directory_scan['dir_count']}")
                    st.write(f"파일 수: {directory_scan['file_count']}")
                    st.write(f"총 크기: {bytes_to_text(int(directory_scan['total_bytes']))}")
                    if directory_scan["sample_entries"]:
                        st.code("\n".join(directory_scan["sample_entries"]), language="text")
            else:
                st.caption("로컬 디렉토리 경로를 입력하면 전체 파일/디렉토리를 스캔합니다.")

        with right_col:
            st.subheader("업로드")
            if selected_files and not too_many_files:
                current_file_signature = "|".join(
                    f"{uploaded_file.name}:{uploaded_file.size}"
                    for uploaded_file in selected_files
                )
                file_confirmed = st.session_state.file_transfer_confirmed_file == current_file_signature
                st.code(
                    "\n".join(
                        [
                            f"file_count: {len(selected_files)}",
                            f"total_size: {bytes_to_text(sum(file.size for file in selected_files))}",
                            *[
                                f"file_{index}: {uploaded_file.name} ({uploaded_file.size} bytes)"
                                for index, uploaded_file in enumerate(selected_files, start=1)
                            ],
                            f"target_root: {file_transfer_root_display}",
                        ]
                    ),
                    language="text",
                )
                if not file_confirmed:
                    if st.button("파일 업로드 확인", use_container_width=True):
                        st.session_state.file_transfer_confirmed_file = current_file_signature
                        st.rerun()
                else:
                    st.warning("파일 업로드 확인이 완료되었습니다. 아래 버튼으로 실제 전송을 실행합니다.")
                    if st.button("파일 업로드 실행", type="primary", use_container_width=True):
                        try:
                            uploaded_results = [
                                upload_selected_file(
                                    config_path,
                                    uploaded_file.name,
                                    uploaded_file.getvalue(),
                                )
                                for uploaded_file in selected_files
                            ]
                        except Exception as exc:  # pragma: no cover - UI error path
                            st.exception(exc)
                        else:
                            st.session_state.file_transfer_confirmed_file = ""
                            st.session_state.file_uploader_nonce += 1
                            st.success(f"업로드 완료: {len(uploaded_results)}개 파일")
                            for remote_path, remote_url in uploaded_results:
                                st.write(remote_path)
                                st.markdown(f"[원격 URL 열기]({remote_url})")
                            st.rerun()
            else:
                if too_many_files:
                    st.caption("선택 파일 수를 10개 이하로 줄이면 업로드 정보가 표시됩니다.")
                else:
                    st.caption("파일을 선택하면 업로드 정보가 표시됩니다.")

            st.divider()
            st.subheader("디렉토리 업로드")
            if directory_scan is not None:
                current_dir_signature = directory_scan["directory"]
                dir_confirmed = st.session_state.file_transfer_confirmed_dir == current_dir_signature
                target_directory = f"{file_transfer_root_display}/{directory_scan['name']}".rstrip("/")
                st.code(
                    "\n".join(
                        [
                            f"source_dir: {directory_scan['directory']}",
                            f"dir_count: {directory_scan['dir_count']}",
                            f"file_count: {directory_scan['file_count']}",
                            f"total_size: {bytes_to_text(int(directory_scan['total_bytes']))}",
                            f"target_root: {target_directory}",
                        ]
                    ),
                    language="text",
                )
                if not dir_confirmed:
                    if st.button("디렉토리 업로드 확인", use_container_width=True):
                        st.session_state.file_transfer_confirmed_dir = current_dir_signature
                        st.rerun()
                else:
                    st.warning("디렉토리 업로드 확인이 완료되었습니다. 아래 버튼으로 실제 전송을 실행합니다.")
                    if st.button("디렉토리 업로드 실행", type="primary", use_container_width=True):
                        try:
                            remote_dir, remote_url, uploaded_dir_count, uploaded_file_count = upload_directory_tree(
                                config_path,
                                str(directory_scan["directory"]),
                            )
                        except Exception as exc:  # pragma: no cover - UI error path
                            st.exception(exc)
                        else:
                            st.session_state.file_transfer_confirmed_dir = ""
                            st.success(
                                f"업로드 완료: {remote_dir} "
                                f"(dirs: {uploaded_dir_count}, files: {uploaded_file_count})"
                            )
                            st.markdown(f"[원격 URL 열기]({remote_url})")
            elif directory_scan_error:
                st.caption("올바른 디렉토리 경로를 입력하면 업로드 확인 버튼이 표시됩니다.")
            else:
                st.caption("디렉토리 경로를 입력하면 업로드 정보가 표시됩니다.")
    else:
        left_col, right_col = st.columns([1.0, 1.0])
        server_file_paths = st.session_state.get("server_file_paths", [])

        with left_col:
            st.subheader("서버 파일 목록")
            st.caption(f"destination.root: {destination_root_display}")
            if server_file_paths:
                st.selectbox(
                    "파일 선택",
                    options=server_file_paths,
                    key="server_file_selected",
                    on_change=apply_server_file_selection,
                )
                nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
                with nav_col1:
                    st.button("⬅", use_container_width=True, on_click=move_server_file, args=(-1,))
                with nav_col2:
                    st.caption(
                        f"{st.session_state.server_file_index + 1} / {len(server_file_paths)}"
                    )
                with nav_col3:
                    st.button("➡", use_container_width=True, on_click=move_server_file, args=(1,))

                delete_targets = st.multiselect(
                    "삭제할 파일 선택",
                    options=server_file_paths,
                    key="server_file_delete_targets",
                    on_change=reset_transfer_confirmation,
                    args=("server_file_delete_confirmed",),
                )
                if delete_targets:
                    if not st.session_state.server_file_delete_confirmed:
                        if st.button("삭제 확인", use_container_width=True):
                            st.session_state.server_file_delete_confirmed = True
                            st.rerun()
                    else:
                        st.warning("삭제 확인이 완료되었습니다. 아래 버튼으로 실제 삭제를 실행합니다.")
                        if st.button("삭제 실행", type="primary", use_container_width=True):
                            try:
                                deleted_count = delete_server_files(config_path, delete_targets)
                            except Exception as exc:  # pragma: no cover - UI error path
                                st.exception(exc)
                            else:
                                st.session_state.server_file_delete_confirmed = False
                                st.success(f"삭제 완료: {deleted_count}개 파일")
                                st.rerun()
                else:
                    st.session_state.server_file_delete_confirmed = False
            else:
                st.info("destination.root 아래에 파일이 없습니다.")

        with right_col:
            st.subheader("파일 내용")
            selected_server_file = st.session_state.get("server_file_selected", "")
            if selected_server_file:
                try:
                    preview = fetch_server_file_preview(config_path, selected_server_file)
                except Exception as exc:  # pragma: no cover - UI error path
                    st.exception(exc)
                else:
                    st.code(
                        "\n".join(
                            [
                                f"path: {preview['path']}",
                                f"size: {bytes_to_text(int(preview['size']))}",
                                f"type: {preview['kind']}",
                            ]
                        ),
                        language="text",
                    )
                    if preview["kind"] == "image":
                        st.image(preview["bytes"], caption=str(preview["path"]))
                    elif preview["kind"] == "text":
                        st.text_area(
                            "server_file_text",
                            str(preview["text"]),
                            height=500,
                            label_visibility="collapsed",
                        )
                    else:
                        st.code(str(preview["text"]), language="text")
                    st.markdown(f"[원격 URL 열기]({preview['browse_url']})")

                    st.divider()
                    if not st.session_state.server_file_single_delete_confirmed:
                        if st.button("현재 파일 삭제 확인", use_container_width=True):
                            st.session_state.server_file_single_delete_confirmed = True
                            st.rerun()
                    else:
                        st.warning("현재 파일 삭제 확인이 완료되었습니다. 아래 버튼으로 실제 삭제를 실행합니다.")
                        if st.button("현재 파일 삭제 실행", type="primary", use_container_width=True):
                            try:
                                deleted_count = delete_server_files(config_path, [selected_server_file])
                            except Exception as exc:  # pragma: no cover - UI error path
                                st.exception(exc)
                            else:
                                st.session_state.server_file_single_delete_confirmed = False
                                st.success(f"삭제 완료: {deleted_count}개 파일")
                                st.rerun()
            else:
                st.session_state.server_file_single_delete_confirmed = False
                st.caption("서버 파일을 선택하면 내용을 보여줍니다.")

    if telegram_settings_runtime and telegram_settings_runtime["enabled"]:
        time.sleep(telegram_settings_runtime["poll_interval_seconds"])
        st.rerun()


if __name__ == "__main__":
    main()
