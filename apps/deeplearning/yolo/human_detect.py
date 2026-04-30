from __future__ import annotations

import configparser
from dataclasses import dataclass
from datetime import datetime
import io
import json
import posixpath
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont, ImageOps
import requests
import streamlit as st
import torch
from ultralytics import YOLO


APP_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = APP_DIR / "output" / "human_detect"
ORIGINAL_OUTPUT_DIR = OUTPUT_DIR / "original"
BOXED_OUTPUT_DIR = OUTPUT_DIR / "boxed"
SETTINGS_PATH = APP_DIR / "human_detect_settings.json"
INPUT_CONF_PATH = APP_DIR / "input.conf"
REQUEST_TIMEOUT = 90
WEBDAV_NS = {"d": "DAV:"}
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
DEFAULT_CONFIDENCE = 0.35


@dataclass
class WebDAVConfig:
    hostname: str
    webdav_root: str
    username: str
    password: str


def get_available_inference_devices() -> list[str]:
    """Return selectable inference devices, preferring CUDA GPUs first."""
    if torch.cuda.is_available():
        return [f"cuda:{index}" for index in range(torch.cuda.device_count())]
    return ["cpu"]


def get_default_inference_device() -> str:
    """Return the default inference device."""
    devices = get_available_inference_devices()
    return devices[0] if devices else "cpu"


def get_device_label(device: str) -> str:
    """Return a human-readable label for the selected inference device."""
    if device.startswith("cuda") and torch.cuda.is_available():
        index = 0
        try:
            index = int(device.split(":")[1])
        except (IndexError, ValueError):
            index = 0
        return f"{device} ({torch.cuda.get_device_name(index)})"
    return device


def load_settings() -> dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_input_conf() -> dict[str, Any]:
    """Load optional INI defaults from input.conf."""
    if not INPUT_CONF_PATH.exists():
        return {}

    parser = configparser.ConfigParser()
    parser.read(INPUT_CONF_PATH, encoding="utf-8")

    source = parser["source"] if parser.has_section("source") else {}
    destination = parser["destination"] if parser.has_section("destination") else {}
    model = parser["model"] if parser.has_section("model") else {}

    return {
        "source": {
            "webdav_hostname": source.get("webdav_hostname", ""),
            "webdav_root": source.get("webdav_root", "/remote.php/dav/files/username/"),
            "username": source.get("username", ""),
            "password": source.get("password", ""),
            "folder": source.get("folder", ""),
        },
        "destinations": {
            "webdav_folders": [
                destination.get("webdav_folder1", ""),
                destination.get("webdav_folder2", ""),
                destination.get("webdav_folder3", ""),
                destination.get("webdav_folder4", ""),
            ],
            "local_folders": [
                destination.get("local_folder1", ""),
                destination.get("local_folder2", ""),
                destination.get("local_folder3", ""),
                destination.get("local_folder4", ""),
            ],
        },
        "model": {
            "name": model.get("name", "yolov8n.pt"),
            "confidence": float(model.get("confidence", str(DEFAULT_CONFIDENCE))),
            "device": model.get("device", get_default_inference_device()),
        },
    }


def save_settings(settings: dict[str, Any]) -> None:
    SETTINGS_PATH.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def normalize_root(root: str) -> str:
    return root.strip("/")


def normalize_remote_path(path: str) -> str:
    return path.strip("/")


def compose_webdav_url(config: WebDAVConfig, remote_path: str = "") -> str:
    host = config.hostname.rstrip("/")
    root = normalize_root(config.webdav_root)
    path = normalize_remote_path(remote_path)
    if root and path:
        encoded = "/".join(quote(part) for part in path.split("/") if part)
        return f"{host}/{root}/{encoded}"
    if root:
        return f"{host}/{root}"
    if path:
        encoded = "/".join(quote(part) for part in path.split("/") if part)
        return f"{host}/{encoded}"
    return host


def build_session(config: WebDAVConfig) -> requests.Session:
    session = requests.Session()
    session.auth = (config.username, config.password)
    return session


def parse_webdav_time(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def propfind(session: requests.Session, url: str, depth: str = "1") -> ET.Element:
    response = session.request(
        "PROPFIND",
        url,
        headers={"Depth": depth},
        data=(
            '<?xml version="1.0" encoding="utf-8" ?>'
            '<d:propfind xmlns:d="DAV:"><d:prop>'
            "<d:resourcetype/><d:getlastmodified/><d:creationdate/><d:getcontentlength/>"
            "</d:prop></d:propfind>"
        ),
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return ET.fromstring(response.text)


def list_remote_images(config: WebDAVConfig, source_folder: str) -> list[dict[str, Any]]:
    session = build_session(config)
    normalized_root = normalize_remote_path(source_folder)
    queue = [normalized_root]
    files: list[dict[str, Any]] = []
    visited: set[str] = set()

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)

        root = propfind(session, compose_webdav_url(config, current), depth="1")
        for response_element in root.findall("d:response", WEBDAV_NS):
            href = response_element.findtext("d:href", default="", namespaces=WEBDAV_NS)
            if not href:
                continue

            parsed_href = urlparse(unquote(href)).path.strip("/")
            expected_prefix = normalize_root(config.webdav_root)
            relative_path = parsed_href[len(expected_prefix):].strip("/") if parsed_href.startswith(expected_prefix) else parsed_href
            if relative_path == current:
                continue

            prop = response_element.find("d:propstat/d:prop", WEBDAV_NS)
            if prop is None:
                continue

            is_collection = prop.find("d:resourcetype/d:collection", WEBDAV_NS) is not None
            if is_collection:
                queue.append(relative_path)
                continue

            extension = Path(relative_path).suffix.lower()
            if extension not in SUPPORTED_IMAGE_EXTENSIONS:
                continue

            files.append(
                {
                    "remote_path": relative_path,
                    "name": Path(relative_path).name,
                    "modified_at": parse_webdav_time(prop.findtext("d:getlastmodified", default="", namespaces=WEBDAV_NS)),
                    "created_at": parse_webdav_time(prop.findtext("d:creationdate", default="", namespaces=WEBDAV_NS)),
                    "size": int(prop.findtext("d:getcontentlength", default="0", namespaces=WEBDAV_NS) or 0),
                }
            )

    return sorted(files, key=lambda item: item["remote_path"])


def download_remote_file(config: WebDAVConfig, remote_path: str) -> bytes:
    session = build_session(config)
    response = session.get(compose_webdav_url(config, remote_path), timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.content


def ensure_remote_directories(session: requests.Session, config: WebDAVConfig, remote_dir: str) -> None:
    normalized = normalize_remote_path(remote_dir)
    if not normalized:
        return

    parts = normalized.split("/")
    current = ""
    for part in parts:
        current = f"{current}/{part}".strip("/")
        url = compose_webdav_url(config, current)
        response = session.request("MKCOL", url, timeout=REQUEST_TIMEOUT)
        if response.status_code not in {201, 301, 405}:
            response.raise_for_status()


def upload_remote_file(config: WebDAVConfig, remote_path: str, data: bytes) -> None:
    session = build_session(config)
    parent_dir = posixpath.dirname(normalize_remote_path(remote_path))
    ensure_remote_directories(session, config, parent_dir)
    response = session.put(
        compose_webdav_url(config, remote_path),
        data=data,
        headers={"Content-Type": "application/octet-stream"},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()


def delete_remote_file(config: WebDAVConfig, remote_path: str) -> None:
    session = build_session(config)
    response = session.delete(compose_webdav_url(config, remote_path), timeout=REQUEST_TIMEOUT)
    response.raise_for_status()


@st.cache_resource
def load_model(model_name: str, device: str) -> YOLO:
    model = YOLO(model_name)
    model.to(device)
    return model


def footer_timestamp(image: Image.Image, timestamp_text: str) -> Image.Image:
    font = ImageFont.load_default()
    draw_probe = ImageDraw.Draw(image)
    text_bbox = draw_probe.textbbox((0, 0), timestamp_text, font=font)
    text_height = text_bbox[3] - text_bbox[1]
    footer_height = max(42, text_height + 18)

    canvas = Image.new("RGB", (image.width, image.height + footer_height), color=(0, 0, 0))
    canvas.paste(image, (0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, image.height, image.width, image.height + footer_height), fill=(20, 20, 20))
    draw.text((12, image.height + 8), timestamp_text, fill=(255, 255, 255), font=font)
    return canvas


def draw_person_boxes(image: Image.Image, boxes: list[dict[str, Any]], timestamp_text: str) -> Image.Image:
    boxed = image.copy()
    draw = ImageDraw.Draw(boxed)
    font = ImageFont.load_default()

    for box in boxes:
        x1, y1, x2, y2 = box["xyxy"]
        confidence = box["confidence"]
        draw.rectangle((x1, y1, x2, y2), outline=(255, 80, 80), width=4)
        label = f"person {confidence:.2f}"
        label_box = draw.textbbox((x1, y1), label, font=font)
        draw.rectangle(
            (
                label_box[0] - 4,
                label_box[1] - 2,
                label_box[2] + 4,
                label_box[3] + 2,
            ),
            fill=(255, 80, 80),
        )
        draw.text((x1, max(0, y1 - 2)), label, fill=(0, 0, 0), font=font)

    return footer_timestamp(boxed, timestamp_text)


def detect_persons(image_bytes: bytes, model_name: str, confidence_threshold: float, device: str) -> dict[str, Any]:
    image = Image.open(io.BytesIO(image_bytes))
    image = ImageOps.exif_transpose(image).convert("RGB")
    model = load_model(model_name, device)
    results = model.predict(image, conf=confidence_threshold, verbose=False, device=device)
    result = results[0]

    person_boxes: list[dict[str, Any]] = []
    if result.boxes is not None:
        for index, cls_value in enumerate(result.boxes.cls.tolist()):
            if int(cls_value) != 0:
                continue
            xyxy = result.boxes.xyxy[index].tolist()
            confidence = float(result.boxes.conf[index].item())
            person_boxes.append(
                {
                    "xyxy": [int(value) for value in xyxy],
                    "confidence": confidence,
                }
            )

    return {
        "image": image,
        "person_boxes": person_boxes,
        "has_person": bool(person_boxes),
    }


def save_image_bytes(image: Image.Image, output_path: Path) -> bytes:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=95)
    data = buffer.getvalue()
    output_path.write_bytes(data)
    return data


def distribute_to_local_dirs(relative_dir: str, file_name: str, data: bytes, destination_dirs: list[str]) -> list[str]:
    saved_paths: list[str] = []
    for destination_dir in [item.strip() for item in destination_dirs if item.strip()]:
        target_dir = Path(destination_dir).expanduser()
        if relative_dir:
            target_dir = target_dir / Path(relative_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / file_name
        target_path.write_bytes(data)
        saved_paths.append(str(target_path))
    return saved_paths


def distribute_to_webdav_dirs(
    relative_dir: str,
    file_name: str,
    data: bytes,
    config: WebDAVConfig,
    destination_dirs: list[str],
) -> list[str]:
    uploaded_paths: list[str] = []
    for destination_dir in [item.strip() for item in destination_dirs if item.strip()]:
        base_dir = normalize_remote_path(destination_dir)
        target_dir = posixpath.join(base_dir, relative_dir).strip("/") if relative_dir else base_dir
        remote_path = posixpath.join(target_dir, file_name).strip("/")
        upload_remote_file(config, remote_path, data)
        uploaded_paths.append(remote_path)
    return uploaded_paths


def default_settings() -> dict[str, Any]:
    return {
        "source": {
            "webdav_hostname": "",
            "webdav_root": "/remote.php/dav/files/username/",
            "username": "",
            "password": "",
            "folder": "",
        },
        "destinations": {
            "webdav_folders": ["", "", "", ""],
            "local_folders": [
                str((OUTPUT_DIR / "export_a").resolve()),
                str((OUTPUT_DIR / "export_b").resolve()),
                "",
                "",
            ],
        },
        "model": {
            "name": "yolov8n.pt",
            "confidence": DEFAULT_CONFIDENCE,
            "device": get_default_inference_device(),
        },
    }


def get_settings() -> dict[str, Any]:
    settings = default_settings()
    input_conf = load_input_conf()
    for key, value in input_conf.items():
        if isinstance(value, dict) and isinstance(settings.get(key), dict):
            settings[key].update(value)
        else:
            settings[key] = value
    saved = load_settings()
    for key, value in saved.items():
        if isinstance(value, dict) and isinstance(settings.get(key), dict):
            settings[key].update(value)
        else:
            settings[key] = value
    return settings


def build_config_from_ui(prefix: str) -> WebDAVConfig:
    return WebDAVConfig(
        hostname=st.session_state[f"{prefix}_webdav_hostname"].strip(),
        webdav_root=st.session_state[f"{prefix}_webdav_root"].strip(),
        username=st.session_state[f"{prefix}_username"].strip(),
        password=st.session_state[f"{prefix}_password"],
    )


def validate_source_config(config: WebDAVConfig, source_folder: str) -> None:
    if not config.hostname or not config.webdav_root or not config.username or not config.password:
        raise ValueError("WebDAV source connection information is incomplete.")
    if not source_folder.strip():
        raise ValueError("Source WebDAV folder is required.")


def process_remote_images(
    source_config: WebDAVConfig,
    source_folder: str,
    destination_webdav_dirs: list[str],
    destination_local_dirs: list[str],
    model_name: str,
    confidence_threshold: float,
    device: str,
) -> list[dict[str, Any]]:
    remote_files = list_remote_images(source_config, source_folder)
    if not remote_files:
        return []

    results: list[dict[str, Any]] = []
    progress = st.progress(0.0, text="Starting human detection...")
    total = len(remote_files)

    destination_webdav_config = source_config

    for index, item in enumerate(remote_files, start=1):
        progress.progress(index / total, text=f"Processing {item['remote_path']}")
        image_bytes = download_remote_file(source_config, item["remote_path"])
        detection = detect_persons(image_bytes, model_name, confidence_threshold, device)

        timestamp = item.get("created_at") or item.get("modified_at") or datetime.now()
        timestamp_text = f"Captured: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        relative_dir = posixpath.dirname(posixpath.relpath(item["remote_path"], normalize_remote_path(source_folder)))
        if relative_dir == ".":
            relative_dir = ""

        result_row: dict[str, Any] = {
            "remote_path": item["remote_path"],
            "captured_at": timestamp_text,
            "has_person": detection["has_person"],
            "person_count": len(detection["person_boxes"]),
            "saved_original": "",
            "saved_boxed": "",
            "webdav_targets": [],
            "local_targets": [],
            "moved_source": False,
        }

        if not detection["has_person"]:
            results.append(result_row)
            continue

        stem = Path(item["remote_path"]).stem
        original_name = f"{stem}_original.jpg"
        boxed_name = f"{stem}_person_box.jpg"

        original_image = footer_timestamp(detection["image"], timestamp_text)
        boxed_image = draw_person_boxes(detection["image"], detection["person_boxes"], timestamp_text)

        original_output_path = ORIGINAL_OUTPUT_DIR / relative_dir / original_name
        boxed_output_path = BOXED_OUTPUT_DIR / relative_dir / boxed_name
        original_bytes = save_image_bytes(original_image, original_output_path)
        boxed_bytes = save_image_bytes(boxed_image, boxed_output_path)

        result_row["saved_original"] = str(original_output_path)
        result_row["saved_boxed"] = str(boxed_output_path)

        local_targets: list[str] = []
        local_targets.extend(distribute_to_local_dirs(relative_dir, original_name, original_bytes, destination_local_dirs))
        local_targets.extend(distribute_to_local_dirs(relative_dir, boxed_name, boxed_bytes, destination_local_dirs))
        result_row["local_targets"] = local_targets

        webdav_targets: list[str] = []
        if destination_webdav_dirs:
            webdav_targets.extend(
                distribute_to_webdav_dirs(relative_dir, original_name, original_bytes, destination_webdav_config, destination_webdav_dirs)
            )
            webdav_targets.extend(
                distribute_to_webdav_dirs(relative_dir, boxed_name, boxed_bytes, destination_webdav_config, destination_webdav_dirs)
            )
        result_row["webdav_targets"] = webdav_targets

        if local_targets or webdav_targets:
            delete_remote_file(source_config, item["remote_path"])
            result_row["moved_source"] = True

        results.append(result_row)

    progress.empty()
    return results


def main() -> None:
    st.set_page_config(page_title="Human Detect", layout="wide")
    st.title("Human Detect")
    st.caption("Read images from WebDAV, detect people, save original and boxed results, then distribute outputs to WebDAV and local folders.")

    ORIGINAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    BOXED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    settings = get_settings()
    source_settings = settings["source"]
    destination_settings = settings["destinations"]
    model_settings = settings["model"]

    with st.sidebar:
        st.header("Model")
        model_name = st.text_input("YOLO Model", value=model_settings["name"], key="model_name")
        available_devices = get_available_inference_devices()
        saved_device = str(model_settings.get("device", get_default_inference_device())).strip() or get_default_inference_device()
        if saved_device not in available_devices:
            saved_device = available_devices[0]
        selected_device = st.selectbox(
            "Inference Device",
            options=available_devices,
            index=available_devices.index(saved_device),
            format_func=get_device_label,
            key="inference_device",
        )
        st.write(f"Selected device: `{get_device_label(selected_device)}`")
        confidence_threshold = st.slider(
            "Confidence Threshold",
            min_value=0.05,
            max_value=0.95,
            value=float(model_settings["confidence"]),
            step=0.05,
            key="confidence_threshold",
        )
        st.caption("Default person class is COCO class 0 from Ultralytics YOLO.")

    left_col, right_col = st.columns(2, gap="large")

    with left_col:
        st.subheader("Source WebDAV")
        st.text_input("Hostname", value=source_settings["webdav_hostname"], key="source_webdav_hostname", placeholder="https://nextcloud.example.com")
        st.text_input("WebDAV Root", value=source_settings["webdav_root"], key="source_webdav_root", placeholder="/remote.php/dav/files/username/")
        st.text_input("Username", value=source_settings["username"], key="source_username")
        st.text_input("Password", value=source_settings["password"], key="source_password", type="password")
        st.text_input("Source Folder", value=source_settings["folder"], key="source_folder", placeholder="Photos/inbox")

        st.subheader("Destination WebDAV Folders")
        for index in range(4):
            value = destination_settings["webdav_folders"][index] if index < len(destination_settings["webdav_folders"]) else ""
            st.text_input(
                f"WebDAV Folder {index + 1}",
                value=value,
                key=f"destination_webdav_folder_{index + 1}",
                placeholder="Photos/human-detect",
            )

    with right_col:
        st.subheader("Destination Local Folders")
        for index in range(4):
            value = destination_settings["local_folders"][index] if index < len(destination_settings["local_folders"]) else ""
            st.text_input(
                f"Local Folder {index + 1}",
                value=value,
                key=f"destination_local_folder_{index + 1}",
                placeholder=str((OUTPUT_DIR / "export").resolve()),
            )

        st.subheader("Output Folders")
        st.write(f"Original output: `{ORIGINAL_OUTPUT_DIR}`")
        st.write(f"Boxed output: `{BOXED_OUTPUT_DIR}`")

    destination_webdav_dirs = [st.session_state.get(f"destination_webdav_folder_{index + 1}", "").strip() for index in range(4)]
    destination_local_dirs = [st.session_state.get(f"destination_local_folder_{index + 1}", "").strip() for index in range(4)]

    save_settings_clicked = st.button("Save Settings", use_container_width=True)
    process_clicked = st.button("Run Human Detection", type="primary", use_container_width=True)

    if save_settings_clicked:
        save_settings(
            {
                "source": {
                    "webdav_hostname": st.session_state["source_webdav_hostname"].strip(),
                    "webdav_root": st.session_state["source_webdav_root"].strip(),
                    "username": st.session_state["source_username"].strip(),
                    "password": st.session_state["source_password"],
                    "folder": st.session_state["source_folder"].strip(),
                },
                "destinations": {
                    "webdav_folders": destination_webdav_dirs,
                    "local_folders": destination_local_dirs,
                },
                "model": {
                    "name": st.session_state["model_name"].strip(),
                    "confidence": float(st.session_state["confidence_threshold"]),
                    "device": st.session_state["inference_device"],
                },
            }
        )
        st.success("Settings saved.")

    if process_clicked:
        try:
            source_config = build_config_from_ui("source")
            source_folder = st.session_state["source_folder"].strip()
            validate_source_config(source_config, source_folder)
            rows = process_remote_images(
                source_config=source_config,
                source_folder=source_folder,
                destination_webdav_dirs=destination_webdav_dirs,
                destination_local_dirs=destination_local_dirs,
                model_name=st.session_state["model_name"].strip(),
                confidence_threshold=float(st.session_state["confidence_threshold"]),
                device=st.session_state["inference_device"],
            )
            if not rows:
                st.info("No image files were found in the source WebDAV folder.")
            else:
                st.success(f"Processed {len(rows)} file(s).")
                st.dataframe(rows, use_container_width=True)

                positives = [row for row in rows if row["has_person"]]
                if positives:
                    latest = positives[-1]
                    if latest["saved_original"]:
                        st.image(str(latest["saved_original"]), caption="Saved original with timestamp", use_container_width=True)
                    if latest["saved_boxed"]:
                        st.image(str(latest["saved_boxed"]), caption="Saved boxed image with timestamp", use_container_width=True)
        except Exception as exc:
            st.error(f"Human detection run failed: {exc}")


if __name__ == "__main__":
    main()
