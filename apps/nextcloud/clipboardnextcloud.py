#!/usr/bin/env python3
"""Streamlit app that previews clipboard contents and uploads them to Nextcloud."""

from __future__ import annotations

import base64
import importlib.util
import json
import os
import posixpath
import re
import socket
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


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
if str(FILESYSTEM_DIR) not in sys.path:
    sys.path.insert(0, str(FILESYSTEM_DIR))

from common import build_client, compose_remote_url, load_config, normalize_root  # noqa: E402


APP_TITLE = "Clipboard to Nextcloud"
DEFAULT_CONFIG = CURRENT_DIR / "input.conf"
SUPPORTED_TARGET_SECTIONS = ("target", "destination")


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

if let items = pasteboard.pasteboardItems, !items.isEmpty {
    let firstItem = items[0]

    if let text = firstItem.string(forType: .string), !text.isEmpty {
        payload["text"] = text
        appendType("text")
    }

    if let htmlData = firstItem.data(forType: .html),
       let html = String(data: htmlData, encoding: .utf8),
       !html.isEmpty {
        payload["html"] = html
        appendType("html")
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

    var imageData = firstItem.data(forType: .png)
    if imageData == nil,
       let tiffData = firstItem.data(forType: .tiff),
       let image = NSImage(data: tiffData),
       let tiffRepresentation = image.tiffRepresentation,
       let bitmap = NSBitmapImageRep(data: tiffRepresentation) {
        imageData = bitmap.representation(using: .png, properties: [:])
    }

    if let imageData, !imageData.isEmpty {
        payload["image_base64"] = imageData.base64EncodedString()
        appendType("image")
    }
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


def ensure_remote_dir(client: Any, remote_dir: str) -> None:
    """Create the target directory tree on Nextcloud if needed."""

    if not remote_dir:
        return

    current = ""
    for part in remote_dir.strip("/").split("/"):
        current = posixpath.join(current, part) if current else part
        if not client.check(current):
            client.mkdir(current)


def build_markdown(payload: Dict[str, Any], created_at: datetime, device_name: str) -> str:
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
        lines.extend(
            [
                "## Image",
                "",
                f'<img alt="clipboard image" src="data:image/png;base64,{image_base64}" />',
                "",
            ]
        )

    if not has_content:
        lines.extend(["클립보드에서 표시 가능한 텍스트/이미지 데이터를 찾지 못했습니다.", ""])

    return "\n".join(lines)


def upload_markdown(config_path: str, payload: Dict[str, Any]) -> Tuple[str, str]:
    """Upload a generated markdown file to Nextcloud and return path/url."""

    section, root, verify_ssl = load_target_section(config_path)
    client = build_client(section, verify_ssl)
    ensure_remote_dir(client, root)

    created_at = datetime.now().astimezone()
    device_name = detect_device_name()
    filename = f"{created_at.strftime('%Y%m%d_%H%M%S')}_{device_name}_clipboard.md"
    remote_path = posixpath.join(root, filename) if root else filename
    markdown = build_markdown(payload, created_at, device_name)

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

    return remote_path, compose_remote_url(section, remote_path)


def render_clipboard_preview(payload: Dict[str, Any]) -> None:
    """Render clipboard contents in the Streamlit UI."""

    types = payload.get("types") or []
    st.caption(f"감지된 타입: {', '.join(types) if types else '없음'}")

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


def main() -> None:
    """Render the Streamlit app."""

    st.set_page_config(page_title=APP_TITLE, page_icon="📋", layout="wide")
    st.title("📋 Clipboard to Nextcloud")
    st.write("현재 macOS 클립보드를 미리 보고, Nextcloud 대상 디렉토리에 Markdown 파일로 업로드합니다.")

    if "clipboard_payload" not in st.session_state:
        st.session_state.clipboard_payload = read_clipboard_payload()

    with st.sidebar:
        st.header("설정")
        config_path = st.text_input("Config path", value=str(DEFAULT_CONFIG))
        st.caption("`[target]` 또는 `[destination]` 섹션을 사용합니다.")

        try:
            section, root, verify_ssl = load_target_section(config_path)
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

        if st.button("클립보드 새로고침", use_container_width=True):
            st.session_state.clipboard_payload = read_clipboard_payload()
            st.rerun()

    payload = st.session_state.clipboard_payload

    left_col, right_col = st.columns([1.2, 0.8])

    with left_col:
        st.subheader("클립보드 미리보기")
        render_clipboard_preview(payload)

    with right_col:
        st.subheader("업로드")
        created_at = datetime.now().astimezone()
        device_name = detect_device_name()
        markdown_preview = build_markdown(payload, created_at, device_name)
        st.code(markdown_preview, language="markdown")

        if st.button("전송", type="primary", use_container_width=True):
            try:
                remote_path, remote_url = upload_markdown(config_path, payload)
            except Exception as exc:  # pragma: no cover - UI error path
                st.exception(exc)
            else:
                st.success(f"업로드 완료: {remote_path}")
                st.markdown(f"[원격 URL 열기]({remote_url})")


if __name__ == "__main__":
    main()
