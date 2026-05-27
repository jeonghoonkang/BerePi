#!/usr/bin/env python3
from __future__ import annotations

import base64
import binascii
import json
import mimetypes
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HOST = os.getenv("GEMMA_OCR_CLIENT_HOST", "127.0.0.1")
PORT = int(os.getenv("GEMMA_OCR_CLIENT_PORT", "8775"))
BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
DATA_DIR = BASE_DIR / "data"
CONFIG_PATH = DATA_DIR / "client_config.json"
HISTORY_PATH = DATA_DIR / "ocr_history.json"
WEBDAV_HISTORY_PATH = DATA_DIR / "webdav_history.json"
RESULT_WEBDAV_HISTORY_PATH = DATA_DIR / "result_webdav_history.json"
SAMPLE_CONFIG_PATH = BASE_DIR / "config" / "client_config.sample.json"
HISTORY_LIMIT = 100
WEBDAV_HISTORY_LIMIT = 20
RESULT_WEBDAV_HISTORY_LIMIT = 50
WEBDAV_SEARCH_LIMIT = 100

DEFAULT_CONFIG = {
    "server_base_url": "http://keti-ev1.iptime.org:8082",
    "generate_path": "/api/generate",
    "status_path": "/api/status",
    "request_timeout_seconds": 600,
    "user_id": "admin",
    "password": "aimodel",
    "model": "",
    "keep_alive": "60m",
    "num_ctx": 8192,
    "ocr_prompt": "Extract all visible text from the image. Preserve line breaks and reading order. Return only the OCR text.",
    "webdav_url": "",
    "webdav_user": "",
    "webdav_password": "",
    "webdav_slots": [
        {"slot": 1, "url": "", "username": "", "password": ""},
        {"slot": 2, "url": "", "username": "", "password": ""},
    ],
    "result_webdav_url": "",
    "result_webdav_sub_path": "",
    "result_webdav_user": "",
    "result_webdav_password": "",
}

TEST_IMAGE_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        sample = DEFAULT_CONFIG
        if SAMPLE_CONFIG_PATH.exists():
            try:
                sample = normalize_config(json.loads(SAMPLE_CONFIG_PATH.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, ValueError):
                sample = DEFAULT_CONFIG
        CONFIG_PATH.write_text(json.dumps(sample, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not HISTORY_PATH.exists():
        HISTORY_PATH.write_text("[]\n", encoding="utf-8")
    if not WEBDAV_HISTORY_PATH.exists():
        WEBDAV_HISTORY_PATH.write_text("[]\n", encoding="utf-8")
    if not RESULT_WEBDAV_HISTORY_PATH.exists():
        RESULT_WEBDAV_HISTORY_PATH.write_text("[]\n", encoding="utf-8")


def normalize_webdav_slot_number(value: Any) -> int:
    try:
        slot = int(value)
    except (TypeError, ValueError):
        return 1
    return 2 if slot == 2 else 1


def normalize_webdav_slots(incoming: dict[str, Any]) -> list[dict[str, Any]]:
    raw_slots = incoming.get("webdav_slots")
    slots_by_number: dict[int, dict[str, Any]] = {}
    if isinstance(raw_slots, list):
        for index, item in enumerate(raw_slots[:2], start=1):
            if not isinstance(item, dict):
                continue
            slot = normalize_webdav_slot_number(item.get("slot", index))
            slots_by_number[slot] = {
                "slot": slot,
                "url": str(item.get("url") or item.get("webdav_url") or "").strip(),
                "username": str(item.get("username") or item.get("user") or item.get("webdav_user") or "").strip(),
                "password": str(item.get("password") or item.get("webdav_password") or ""),
            }

    if 1 not in slots_by_number:
        slots_by_number[1] = {
            "slot": 1,
            "url": str(incoming.get("webdav_url") or "").strip(),
            "username": str(incoming.get("webdav_user") or "").strip(),
            "password": str(incoming.get("webdav_password") or ""),
        }
    if 2 not in slots_by_number:
        slots_by_number[2] = {"slot": 2, "url": "", "username": "", "password": ""}

    return [slots_by_number[1], slots_by_number[2]]


def normalize_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    incoming = dict(raw or {})
    timeout = int(incoming.get("request_timeout_seconds") or DEFAULT_CONFIG["request_timeout_seconds"])
    num_ctx = int(incoming.get("num_ctx") or DEFAULT_CONFIG["num_ctx"])
    webdav_slots = normalize_webdav_slots(incoming)
    return {
        "server_base_url": str(incoming.get("server_base_url") or DEFAULT_CONFIG["server_base_url"]).rstrip("/"),
        "generate_path": str(incoming.get("generate_path") or DEFAULT_CONFIG["generate_path"]),
        "status_path": str(incoming.get("status_path") or DEFAULT_CONFIG["status_path"]),
        "request_timeout_seconds": max(5, timeout),
        "user_id": str(incoming.get("user_id") or ""),
        "password": str(incoming.get("password") or ""),
        "model": str(incoming.get("model") or ""),
        "keep_alive": str(incoming.get("keep_alive") or DEFAULT_CONFIG["keep_alive"]),
        "num_ctx": max(0, num_ctx),
        "ocr_prompt": str(incoming.get("ocr_prompt") or DEFAULT_CONFIG["ocr_prompt"]),
        "webdav_url": webdav_slots[0]["url"],
        "webdav_user": webdav_slots[0]["username"],
        "webdav_password": webdav_slots[0]["password"],
        "webdav_slots": webdav_slots,
        "result_webdav_url": str(incoming.get("result_webdav_url") or "").strip(),
        "result_webdav_sub_path": str(incoming.get("result_webdav_sub_path") or "").strip().strip("/\\"),
        "result_webdav_user": str(incoming.get("result_webdav_user") or "").strip(),
        "result_webdav_password": str(incoming.get("result_webdav_password") or ""),
    }


def read_config() -> dict[str, Any]:
    ensure_data_files()
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        data = DEFAULT_CONFIG
    return normalize_config(data)


def write_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_config(config)
    CONFIG_PATH.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return normalized


def runtime_config(override: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = read_config()
    for key, value in dict(override or {}).items():
        if key in DEFAULT_CONFIG:
            if key in {"user_id", "password"} and value == "" and merged.get(key):
                continue
            merged[key] = value
    return normalize_config(merged)


def read_history() -> list[dict[str, Any]]:
    ensure_data_files()
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [entry for entry in data[:HISTORY_LIMIT] if isinstance(entry, dict)]


def append_history(entry: dict[str, Any]) -> list[dict[str, Any]]:
    history = [entry] + read_history()
    history = history[:HISTORY_LIMIT]
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return history


def clear_history() -> list[dict[str, Any]]:
    HISTORY_PATH.write_text("[]\n", encoding="utf-8")
    return []


def webdav_slot_config(config: dict[str, Any], slot: int) -> dict[str, Any]:
    slots = config.get("webdav_slots")
    if isinstance(slots, list):
        for item in slots:
            if isinstance(item, dict) and normalize_webdav_slot_number(item.get("slot")) == slot:
                return item
    if slot == 1:
        return {
            "slot": 1,
            "url": str(config.get("webdav_url") or ""),
            "username": str(config.get("webdav_user") or ""),
            "password": str(config.get("webdav_password") or ""),
        }
    return {"slot": 2, "url": "", "username": "", "password": ""}


def webdav_history_entry(config: dict[str, Any] | None = None, incoming: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or {}
    incoming = incoming or {}
    slot = normalize_webdav_slot_number(incoming.get("slot", 1))
    slot_config = webdav_slot_config(config, slot)
    return {
        "slot": slot,
        "url": str(incoming.get("url") or slot_config.get("url") or "").strip(),
        "username": str(incoming.get("username") or slot_config.get("username") or "").strip(),
        "password": str(incoming.get("password") or slot_config.get("password") or ""),
    }


def webdav_history_label(entry: dict[str, Any]) -> str:
    url = str(entry.get("url") or "")
    username = str(entry.get("username") or "")
    slot = normalize_webdav_slot_number(entry.get("slot", 1))
    prefix = f"탭 {slot}: "
    return f"{prefix}{username}@{url}" if username else f"{prefix}{url}"


def read_webdav_history() -> list[dict[str, Any]]:
    ensure_data_files()
    try:
        data = json.loads(WEBDAV_HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        url = str(entry.get("url") or "").strip()
        if not url:
            continue
        cleaned.append(
            {
                "id": str(entry.get("id") or f"webdav-{len(cleaned)+1}"),
                "slot": normalize_webdav_slot_number(entry.get("slot", 1)),
                "url": url,
                "username": str(entry.get("username") or ""),
                "password": str(entry.get("password") or ""),
                "label": str(entry.get("label") or webdav_history_label(entry)),
                "updated_at": str(entry.get("updated_at") or ""),
            }
        )
        if len(cleaned) >= WEBDAV_HISTORY_LIMIT:
            break
    return cleaned


def write_webdav_history(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[tuple[int, str, str]] = set()
    for entry in entries:
        slot = normalize_webdav_slot_number(entry.get("slot", 1))
        url = str(entry.get("url") or "").strip()
        username = str(entry.get("username") or "").strip()
        if not url:
            continue
        key = (slot, url, username)
        if key in seen:
            continue
        normalized = {
            "id": str(entry.get("id") or f"webdav-{int(time.time() * 1000)}-{len(unique)+1}"),
            "slot": slot,
            "url": url,
            "username": username,
            "password": str(entry.get("password") or ""),
            "label": webdav_history_label({"slot": slot, "url": url, "username": username}),
            "updated_at": str(entry.get("updated_at") or time.strftime("%Y-%m-%d %H:%M:%S")),
        }
        unique.append(normalized)
        seen.add(key)
        if len(unique) >= WEBDAV_HISTORY_LIMIT:
            break
    WEBDAV_HISTORY_PATH.write_text(json.dumps(unique, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return unique


def remember_webdav_config(config: dict[str, Any] | None = None, incoming: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    entry = webdav_history_entry(config, incoming)
    if not entry["url"]:
        return read_webdav_history()
    return write_webdav_history([{**entry, "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}] + read_webdav_history())


def remember_webdav_config_slots(config: dict[str, Any]) -> list[dict[str, Any]]:
    entries = [
        {
            "slot": slot["slot"],
            "url": slot["url"],
            "username": slot["username"],
            "password": slot["password"],
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for slot in normalize_webdav_slots(config)
        if str(slot.get("url") or "").strip()
    ]
    if not entries:
        return read_webdav_history()
    return write_webdav_history(entries + read_webdav_history())


def delete_webdav_history_id(entry_id: str) -> list[dict[str, Any]]:
    return write_webdav_history([entry for entry in read_webdav_history() if entry["id"] != str(entry_id)])


def result_webdav_history_entry(
    config: dict[str, Any] | None = None,
    incoming: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or {}
    incoming = incoming or {}
    return {
        "url": str(incoming.get("url") or config.get("result_webdav_url") or "").strip(),
        "sub_path": str(incoming.get("sub_path") or config.get("result_webdav_sub_path") or "").strip().strip("/\\"),
        "username": str(incoming.get("username") or config.get("result_webdav_user") or "").strip(),
        "password": str(incoming.get("password") or config.get("result_webdav_password") or ""),
    }


def result_webdav_history_label(entry: dict[str, Any]) -> str:
    url = str(entry.get("url") or "").rstrip("/")
    sub_path = str(entry.get("sub_path") or "").strip("/\\")
    username = str(entry.get("username") or "")
    path = f"{url}/{sub_path}" if sub_path else url
    return f"{username}@{path}" if username else path


def read_result_webdav_history() -> list[dict[str, Any]]:
    ensure_data_files()
    try:
        data = json.loads(RESULT_WEBDAV_HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        url = str(entry.get("url") or "").strip()
        if not url:
            continue
        normalized = {
            "id": str(entry.get("id") or f"result-webdav-{len(cleaned)+1}"),
            "url": url,
            "sub_path": str(entry.get("sub_path") or "").strip().strip("/\\"),
            "username": str(entry.get("username") or ""),
            "password": str(entry.get("password") or ""),
            "label": str(entry.get("label") or result_webdav_history_label(entry)),
            "updated_at": str(entry.get("updated_at") or ""),
        }
        cleaned.append(normalized)
        if len(cleaned) >= RESULT_WEBDAV_HISTORY_LIMIT:
            break
    return cleaned


def write_result_webdav_history(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for entry in entries:
        url = str(entry.get("url") or "").strip()
        sub_path = str(entry.get("sub_path") or "").strip().strip("/\\")
        username = str(entry.get("username") or "").strip()
        if not url:
            continue
        key = (url, sub_path, username)
        if key in seen:
            continue
        normalized = {
            "id": str(entry.get("id") or f"result-webdav-{int(time.time() * 1000)}-{len(unique)+1}"),
            "url": url,
            "sub_path": sub_path,
            "username": username,
            "password": str(entry.get("password") or ""),
            "label": result_webdav_history_label({"url": url, "sub_path": sub_path, "username": username}),
            "updated_at": str(entry.get("updated_at") or time.strftime("%Y-%m-%d %H:%M:%S")),
        }
        unique.append(normalized)
        seen.add(key)
        if len(unique) >= RESULT_WEBDAV_HISTORY_LIMIT:
            break
    RESULT_WEBDAV_HISTORY_PATH.write_text(json.dumps(unique, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return unique


def remember_result_webdav_config(
    config: dict[str, Any] | None = None,
    incoming: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    entry = result_webdav_history_entry(config, incoming)
    if not entry["url"]:
        return read_result_webdav_history()
    return write_result_webdav_history(
        [{**entry, "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}] + read_result_webdav_history()
    )


def delete_result_webdav_history_id(entry_id: str) -> list[dict[str, Any]]:
    return write_result_webdav_history(
        [entry for entry in read_result_webdav_history() if entry["id"] != str(entry_id)]
    )


def join_url(base_url: str, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def request_json(
    url: str,
    payload: dict[str, Any] | None,
    timeout: int,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if extra_headers:
        headers.update(extra_headers)
    request = urllib.request.Request(url, data=data, headers=headers, method="POST" if payload is not None else "GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            content_type = str(response.headers.get("Content-Type") or "")
            if not raw.strip():
                raise ValueError(f"Empty response from {url}")
            try:
                return json.loads(raw)
            except json.JSONDecodeError as exc:
                preview = raw.strip().replace("\n", " ")[:220]
                raise ValueError(
                    f"Expected JSON from {url}, but received Content-Type={content_type or 'unknown'}; "
                    f"preview={preview!r}"
                ) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise TimeoutError(f"Timed out waiting for {url} after {timeout} seconds.") from exc


def basic_auth_header(config: dict[str, Any]) -> dict[str, str]:
    if not config.get("user_id") or not config.get("password"):
        return {}
    token = base64.b64encode(f"{config['user_id']}:{config['password']}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def webdav_auth_header(config: dict[str, Any]) -> dict[str, str]:
    user = str(config.get("webdav_user") or config.get("username") or "")
    password = str(config.get("webdav_password") or config.get("password") or "")
    if not user and not password:
        return {}
    token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def clean_path_segments(path: str) -> list[str]:
    return [segment for segment in str(path or "").replace("\\", "/").split("/") if segment]


def quote_path_segments(path: str) -> str:
    return "/".join(urllib.parse.quote(segment, safe="") for segment in clean_path_segments(path))


def join_webdav_output_url(base_url: str, sub_path: str, file_name: str) -> str:
    target = base_url.rstrip("/")
    quoted_sub_path = quote_path_segments(sub_path)
    if quoted_sub_path:
        target = f"{target}/{quoted_sub_path}"
    return f"{target}/{urllib.parse.quote(file_name, safe='')}"


def safe_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return cleaned or "host"


def ocr_result_file_name() -> str:
    host = safe_filename_part(socket.gethostname())
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    milliseconds = int((time.time() % 1) * 1000)
    return f"{host}_{timestamp}_{milliseconds:03d}.txt"


def ensure_webdav_sub_path(base_url: str, sub_path: str, headers: dict[str, str], timeout: int) -> None:
    current = base_url.rstrip("/")
    for segment in clean_path_segments(sub_path):
        current = f"{current}/{urllib.parse.quote(segment, safe='')}"
        request = urllib.request.Request(current, headers=headers, method="MKCOL")
        try:
            with urllib.request.urlopen(request, timeout=timeout):
                pass
        except urllib.error.HTTPError as exc:
            if exc.code in {HTTPStatus.METHOD_NOT_ALLOWED, HTTPStatus.CONFLICT}:
                continue
            raise ValueError(f"Could not create WebDAV output sub path: {current} | HTTP {exc.code} {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise ValueError(f"Could not create WebDAV output sub path: {current} | {exc}") from exc


def image_name_from_url(url: str) -> str:
    path = urllib.parse.urlsplit(url).path
    name = Path(urllib.parse.unquote(path)).name
    return name or f"webdav-image-{int(time.time())}.png"


def absolute_webdav_url(base_url: str, href: str) -> str:
    if href.startswith(("http://", "https://")):
        return href
    parsed = urllib.parse.urlsplit(base_url)
    if href.startswith("/"):
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, href, "", ""))
    return urllib.parse.urljoin(base_url.rstrip("/") + "/", href)


def webdav_request_context(config: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    slot = normalize_webdav_slot_number(incoming.get("slot", 1))
    slot_config = webdav_slot_config(config, slot)
    url = str(incoming.get("url") or slot_config.get("url") or "").strip()
    if not url:
        raise ValueError("WebDAV image URL is required.")
    if not url.startswith(("http://", "https://")):
        raise ValueError("WebDAV image URL must start with http:// or https://.")

    merged_config = {
        "username": str(slot_config.get("username") or ""),
        "password": str(slot_config.get("password") or ""),
    }
    for source_key in ("username", "password"):
        if source_key in incoming:
            merged_config[source_key] = str(incoming.get(source_key) or "")

    headers = {"Accept": "image/*,*/*;q=0.8", **webdav_auth_header(merged_config)}
    return {"slot": slot, "url": url, "headers": headers, "name": image_name_from_url(url)}


def parse_content_length(headers: Any) -> int | None:
    content_range = str(headers.get("Content-Range") or "")
    if "/" in content_range:
        total = content_range.rsplit("/", 1)[-1].strip()
        if total.isdigit():
            return int(total)
    content_length = str(headers.get("Content-Length") or "").strip()
    return int(content_length) if content_length.isdigit() else None


def xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def child_text_by_local_name(element: ET.Element, local_name: str) -> str:
    for child in element.iter():
        if xml_local_name(child.tag) == local_name:
            return str(child.text or "").strip()
    return ""


def has_collection_resource_type(element: ET.Element) -> bool:
    for child in element.iter():
        if xml_local_name(child.tag) == "collection":
            return True
    return False


def webdav_image_record(context: dict[str, Any], url: str, name: str, content_type: str, content_length: int | None) -> dict[str, Any]:
    return {
        "id": f"webdav-file-{abs(hash((context['slot'], url, name)))}",
        "slot": context["slot"],
        "name": name,
        "url": url,
        "href": url,
        "content_type": content_type,
        "content_length": content_length,
    }


def search_webdav_images(context: dict[str, Any], timeout: int, limit: int = WEBDAV_SEARCH_LIMIT) -> list[dict[str, Any]]:
    headers = dict(context["headers"])
    headers.update({"Accept": "application/xml,text/xml,*/*;q=0.8", "Content-Type": "application/xml; charset=utf-8", "Depth": "1"})
    body = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<d:propfind xmlns:d="DAV:">'
        "<d:prop><d:resourcetype/><d:getcontenttype/><d:getcontentlength/><d:displayname/></d:prop>"
        "</d:propfind>"
    ).encode("utf-8")
    request = urllib.request.Request(context["url"], data=body, headers=headers, method="PROPFIND")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raise ValueError(f"WebDAV directory search failed: HTTP {exc.code} {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Could not search WebDAV directory: {context['url']} | {exc}") from exc

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError("WebDAV directory search did not return valid XML. Check that the URL is a WebDAV endpoint, not a browser page.") from exc

    images: list[dict[str, Any]] = []
    base_path = urllib.parse.urlsplit(context["url"]).path.rstrip("/")
    for response_element in root.iter():
        if xml_local_name(response_element.tag) != "response":
            continue
        href = child_text_by_local_name(response_element, "href")
        if not href:
            continue
        href_path = urllib.parse.urlsplit(href).path.rstrip("/")
        if href_path == base_path or has_collection_resource_type(response_element):
            continue
        content_type = child_text_by_local_name(response_element, "getcontenttype").split(";", 1)[0].strip().lower()
        display_name = child_text_by_local_name(response_element, "displayname")
        name = display_name or Path(urllib.parse.unquote(href_path)).name
        inferred_type = mimetypes.guess_type(name)[0] or ""
        if not content_type.startswith("image/") and not inferred_type.startswith("image/"):
            continue
        length_text = child_text_by_local_name(response_element, "getcontentlength")
        image_url = absolute_webdav_url(context["url"], href)
        images.append(
            webdav_image_record(
                context,
                image_url,
                name,
                content_type or inferred_type,
                int(length_text) if length_text.isdigit() else None,
            )
        )
        if len(images) >= limit:
            break
    return images


def search_webdav_image_path(config: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    context = webdav_request_context(config, incoming)
    url = context["url"]
    headers = context["headers"]
    started = time.perf_counter()

    request = urllib.request.Request(url, headers=headers, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=int(config["request_timeout_seconds"])) as response:
            status_code = int(getattr(response, "status", 200))
            content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            content_length = parse_content_length(response.headers)
            method = "HEAD"
    except urllib.error.HTTPError as exc:
        if exc.code not in {HTTPStatus.METHOD_NOT_ALLOWED, HTTPStatus.NOT_IMPLEMENTED}:
            raise ValueError(f"WebDAV image path is not accessible: HTTP {exc.code} {exc.reason}") from exc
        range_headers = dict(headers)
        range_headers["Range"] = "bytes=0-0"
        range_request = urllib.request.Request(url, headers=range_headers, method="GET")
        try:
            with urllib.request.urlopen(range_request, timeout=int(config["request_timeout_seconds"])) as response:
                response.read(1)
                status_code = int(getattr(response, "status", 200))
                content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
                content_length = parse_content_length(response.headers)
                method = "GET Range"
        except urllib.error.HTTPError as range_exc:
            raise ValueError(
                f"WebDAV image path is not accessible: HTTP {range_exc.code} {range_exc.reason}"
            ) from range_exc
        except urllib.error.URLError as range_exc:
            raise ValueError(f"Could not test WebDAV image path: {url} | {range_exc}") from range_exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Could not test WebDAV image path: {url} | {exc}") from exc

    inferred_type = mimetypes.guess_type(context["name"])[0] or ""
    is_image = content_type.startswith("image/") or inferred_type.startswith("image/")
    if not is_image:
        matched_images = search_webdav_images(context, int(config["request_timeout_seconds"]))
        if not matched_images:
            raise ValueError(
                f"WebDAV path exists but no image files were found. Content-Type={content_type or 'unknown'}. "
                "Check that the URL is a WebDAV directory or direct image URL, not a browser/share page."
            )
        return {
            "ok": True,
            "slot": context["slot"],
            "url": url,
            "name": context["name"],
            "content_type": content_type or "directory",
            "content_length": content_length,
            "status_code": status_code,
            "method": "PROPFIND",
            "elapsed_seconds": time.perf_counter() - started,
            "matched_image_count": len(matched_images),
            "matched_images": matched_images,
        }

    matched_images = [
        webdav_image_record(context, url, context["name"], content_type or inferred_type, content_length)
    ]
    return {
        "ok": True,
        "slot": context["slot"],
        "url": url,
        "name": context["name"],
        "content_type": content_type or inferred_type,
        "content_length": content_length,
        "status_code": status_code,
        "method": method,
        "elapsed_seconds": time.perf_counter() - started,
        "matched_image_count": len(matched_images),
        "matched_images": matched_images,
    }


def test_webdav_image(config: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    return search_webdav_image_path(config, incoming)


def load_webdav_image(config: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    context = webdav_request_context(config, incoming)
    slot = context["slot"]
    url = context["url"]
    headers = context["headers"]
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=int(config["request_timeout_seconds"])) as response:
            content = response.read()
            content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
    except urllib.error.URLError as exc:
        raise ValueError(f"Could not load WebDAV image: {url} | {exc}") from exc

    name = context["name"]
    inferred_type = mimetypes.guess_type(name)[0] or ""
    mime_type = content_type or inferred_type or "application/octet-stream"
    if not mime_type.startswith("image/"):
        if inferred_type.startswith("image/"):
            mime_type = inferred_type
        else:
            raise ValueError(f"WebDAV URL did not return an image. Content-Type={content_type or 'unknown'}")

    return {
        "name": name,
        "mime_type": mime_type,
        "size": len(content),
        "source": "webdav",
        "slot": slot,
        "content_base64": base64.b64encode(content).decode("ascii"),
        "url": url,
    }


def extract_response_text(data: dict[str, Any]) -> str:
    for key in ("response", "text", "output", "content"):
        value = data.get(key)
        if isinstance(value, str):
            return value
    message = data.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"]
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
            if isinstance(first.get("text"), str):
                return first["text"]
    return json.dumps(data, ensure_ascii=False, indent=2)


def clean_image_item(item: dict[str, Any]) -> dict[str, str]:
    name = str(item.get("name") or "image")
    mime_type = str(item.get("mime_type") or "image/png")
    content_base64 = str(item.get("content_base64") or "")
    source = str(item.get("source") or "")
    url = str(item.get("url") or "")
    if not mime_type.startswith("image/"):
        raise ValueError(f"Only image files are supported: {name}")
    try:
        base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"Invalid image payload for {name}: {exc}") from exc
    cleaned = {"name": name, "mime_type": mime_type, "content_base64": content_base64}
    if source:
        cleaned["source"] = source
    if url:
        cleaned["url"] = url
    return cleaned


def build_generate_payload(config: dict[str, Any], prompt: str, images: list[dict[str, str]]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "user_id": config["user_id"],
        "password": config["password"],
        "prompt": prompt,
        "images": [image["content_base64"] for image in images],
        "keep_alive": config["keep_alive"],
        "stream": False,
        "options": {"num_ctx": int(config["num_ctx"])},
    }
    if config.get("model"):
        payload["model"] = config["model"]
    return payload


def run_ocr(config: dict[str, Any], images: list[dict[str, Any]], prompt: str) -> dict[str, Any]:
    if not config.get("server_base_url"):
        raise ValueError("Gemma model URL is required.")
    if not images:
        raise ValueError("At least one image is required.")
    clean_images = [clean_image_item(item) for item in images]
    effective_prompt = str(prompt or config["ocr_prompt"]).strip()
    if not effective_prompt:
        raise ValueError("OCR prompt is required.")
    generate_url = join_url(config["server_base_url"], config["generate_path"])
    started = time.perf_counter()
    try:
        data = request_json(
            generate_url,
            build_generate_payload(config, effective_prompt, clean_images),
            int(config["request_timeout_seconds"]),
            basic_auth_header(config),
        )
    except urllib.error.HTTPError as exc:
        if exc.code == HTTPStatus.UNAUTHORIZED:
            raise ValueError(
                f"Gemma generate endpoint rejected authentication: {generate_url}. "
                "Check User ID/Password in the left panel, then save settings and retry."
            ) from exc
        raise ValueError(f"Gemma generate endpoint returned HTTP {exc.code}: {generate_url} | {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Could not connect to Gemma generate endpoint: {generate_url} | {exc}") from exc
    except TimeoutError as exc:
        raise ValueError(str(exc)) from exc
    elapsed = time.perf_counter() - started
    text = extract_response_text(data).strip()
    remote_image_count = data.get("image_count")
    if remote_image_count is not None:
        try:
            remote_image_count = int(remote_image_count)
        except (TypeError, ValueError):
            remote_image_count = None
    entry = {
        "id": f"ocr-{int(time.time() * 1000)}",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "server_base_url": config["server_base_url"],
        "generate_url": generate_url,
        "model": str(data.get("model") or config.get("model") or ""),
        "image_names": [image["name"] for image in clean_images],
        "images": [
            {
                "name": image["name"],
                "mime_type": image["mime_type"],
                "source": image.get("source", ""),
                "url": image.get("url", ""),
            }
            for image in clean_images
        ],
        "webdav_urls": [image["url"] for image in clean_images if image.get("source") == "webdav" and image.get("url")],
        "image_count": len(clean_images),
        "server_image_count": remote_image_count,
        "server_response_keys": sorted(str(key) for key in data.keys()),
        "elapsed_seconds": elapsed,
        "text": text,
    }
    return {"result": entry, "raw": data, "history": append_history(entry)}


def save_ocr_result_to_webdav(config: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    entry = result_webdav_history_entry(config, incoming)
    base_url = entry["url"]
    if not base_url:
        raise ValueError("OCR result WebDAV output URL is required.")
    if not base_url.startswith(("http://", "https://")):
        raise ValueError("OCR result WebDAV output URL must start with http:// or https://.")

    content = str(incoming.get("content") or "")
    if not content.strip():
        raise ValueError("OCR result content is empty.")

    timeout = int(config["request_timeout_seconds"])
    headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "Accept": "application/json,text/plain,*/*;q=0.8",
        **webdav_auth_header({"username": entry["username"], "password": entry["password"]}),
    }
    ensure_webdav_sub_path(base_url, entry["sub_path"], headers, timeout)
    file_name = ocr_result_file_name()
    save_url = join_webdav_output_url(base_url, entry["sub_path"], file_name)
    body = content.encode("utf-8")
    request = urllib.request.Request(save_url, data=body, headers=headers, method="PUT")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status_code = int(getattr(response, "status", 200))
            response.read()
    except urllib.error.HTTPError as exc:
        raise ValueError(f"Could not save OCR result to WebDAV: {save_url} | HTTP {exc.code} {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Could not save OCR result to WebDAV: {save_url} | {exc}") from exc

    return {
        "ok": True,
        "url": save_url,
        "file_name": file_name,
        "host": socket.gethostname(),
        "sub_path": entry["sub_path"],
        "status_code": status_code,
        "elapsed_seconds": time.perf_counter() - started,
        "history": remember_result_webdav_config(config, incoming),
    }


def build_image_transfer_test_payload(config: dict[str, Any], images: list[dict[str, Any]]) -> dict[str, Any]:
    clean_images = [clean_image_item(item) for item in images]
    if not clean_images:
        clean_images = [
            {
                "name": "embedded-1x1-test.png",
                "mime_type": "image/png",
                "content_base64": TEST_IMAGE_BASE64,
            }
        ]
    payload: dict[str, Any] = {
        "user_id": config["user_id"],
        "password": config["password"],
        "images": [image["content_base64"] for image in clean_images],
    }
    if config.get("model"):
        payload["model"] = config["model"]
    return payload


def test_image_transfer(config: dict[str, Any], images: list[dict[str, Any]]) -> dict[str, Any]:
    if not config.get("server_base_url"):
        raise ValueError("Gemma model URL is required.")
    url = join_url(config["server_base_url"], "/api/test-image-transfer")
    payload = build_image_transfer_test_payload(config, images)
    image_count = len(payload["images"])
    started = time.perf_counter()
    try:
        data = request_json(url, payload, int(config["request_timeout_seconds"]), basic_auth_header(config))
    except urllib.error.HTTPError as exc:
        if exc.code == HTTPStatus.UNAUTHORIZED:
            raise ValueError(
                f"Gemma image-transfer test endpoint rejected authentication: {url}. "
                "Check User ID/Password in the left panel, then save settings and retry."
            ) from exc
        if exc.code == HTTPStatus.NOT_FOUND:
            raise ValueError(
                f"Image transfer test endpoint not found: {url}. "
                "Restart or update the Gemma server with /api/test-image-transfer support."
            ) from exc
        raise
    except urllib.error.URLError as exc:
        raise ValueError(
            f"Could not connect to Gemma image-transfer test endpoint: {url} | {exc}. "
            "Check the Gemma Model URL in the left panel, save settings, and restart the client service if needed."
        ) from exc
    elapsed = time.perf_counter() - started
    return {
        "ok": bool(data.get("ok")),
        "test_url": url,
        "client_image_count": image_count,
        "server_image_count": data.get("image_count"),
        "elapsed_seconds": elapsed,
        "message": str(data.get("message") or ""),
        "raw": data,
    }


def fetch_remote_status(config: dict[str, Any]) -> dict[str, Any]:
    url = join_url(config["server_base_url"], config["status_path"])
    try:
        data = request_json(url, None, int(config["request_timeout_seconds"]), basic_auth_header(config))
    except urllib.error.URLError as exc:
        raise ValueError(
            f"Could not connect to Gemma status endpoint: {url} | {exc}. "
            "Check the Gemma Model URL in the left panel."
        ) from exc
    return {
        "server_base_url": config["server_base_url"],
        "status_url": url,
        "host": data.get("host", ""),
        "port": data.get("port", ""),
        "model": data.get("model", ""),
        "ollama_reachable": bool(data.get("ollama_reachable", True)),
        "model_available": bool(data.get("model_available", True)),
        "raw": data,
    }


def parse_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8") or "{}")


class ClientHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

    def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_file(self, path: Path, content_type: str) -> None:
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            self.serve_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
            return
        if self.path == "/styles.css":
            self.serve_file(WEB_DIR / "styles.css", "text/css; charset=utf-8")
            return
        if self.path == "/app.js":
            self.serve_file(WEB_DIR / "app.js", "application/javascript; charset=utf-8")
            return
        if self.path == "/api/state":
            self.send_json(
                {
                    "config": read_config(),
                    "history": read_history(),
                    "webdav_history": read_webdav_history(),
                    "result_webdav_history": read_result_webdav_history(),
                }
            )
            return
        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        try:
            incoming = parse_json_body(self)
            request_path = urllib.parse.urlsplit(self.path).path.rstrip("/") or "/"
            if request_path == "/api/config":
                config = write_config(incoming.get("config") or {})
                webdav_history = remember_webdav_config_slots(config)
                result_webdav_history = remember_result_webdav_config(config, {})
                self.send_json(
                    {
                        "config": config,
                        "webdav_history": webdav_history,
                        "result_webdav_history": result_webdav_history,
                    }
                )
                return
            if request_path == "/api/webdav-config/save":
                config = write_config(incoming.get("config") or {})
                webdav_history = remember_webdav_config(config, incoming)
                self.send_json({"config": config, "webdav_history": webdav_history})
                return
            if request_path == "/api/test-connection":
                config = runtime_config(incoming.get("config"))
                self.send_json({"status": fetch_remote_status(config)})
                return
            if request_path == "/api/test-image-transfer":
                config = runtime_config(incoming.get("config"))
                self.send_json({"status": test_image_transfer(config, incoming.get("images") or [])})
                return
            if request_path == "/api/webdav-image":
                config = runtime_config(incoming.get("config"))
                image = load_webdav_image(config, incoming)
                webdav_history = remember_webdav_config(config, incoming)
                self.send_json({"image": image, "webdav_history": webdav_history})
                return
            if request_path == "/api/webdav-image/test":
                config = runtime_config(incoming.get("config"))
                status = test_webdav_image(config, incoming)
                webdav_history = remember_webdav_config(config, incoming)
                self.send_json({"status": status, "webdav_history": webdav_history})
                return
            if request_path == "/api/webdav-image/search":
                config = runtime_config(incoming.get("config"))
                status = search_webdav_image_path(config, incoming)
                webdav_history = remember_webdav_config(config, incoming)
                self.send_json({"status": status, "webdav_history": webdav_history})
                return
            if request_path == "/api/webdav-history/delete":
                self.send_json({"webdav_history": delete_webdav_history_id(str(incoming.get("id") or ""))})
                return
            if request_path == "/api/result-webdav-config/save":
                config = write_config(incoming.get("config") or {})
                result_webdav_history = remember_result_webdav_config(config, incoming)
                self.send_json({"config": config, "result_webdav_history": result_webdav_history})
                return
            if request_path == "/api/result-webdav-history/delete":
                self.send_json(
                    {"result_webdav_history": delete_result_webdav_history_id(str(incoming.get("id") or ""))}
                )
                return
            if request_path == "/api/ocr-result/save-webdav":
                config = runtime_config(incoming.get("config"))
                self.send_json({"status": save_ocr_result_to_webdav(config, incoming)})
                return
            if request_path == "/api/ocr":
                config = runtime_config(incoming.get("config"))
                self.send_json(run_ocr(config, incoming.get("images") or [], str(incoming.get("prompt") or "")))
                return
            if request_path == "/api/history/clear":
                self.send_json({"history": clear_history()})
                return
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except (json.JSONDecodeError, OSError, TimeoutError, urllib.error.URLError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)


def main() -> int:
    ensure_data_files()
    httpd = ThreadingHTTPServer((HOST, PORT), ClientHandler)
    print(f"Gemma OCR client service: http://{HOST}:{PORT}")
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
