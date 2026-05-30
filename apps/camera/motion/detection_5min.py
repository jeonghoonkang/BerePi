#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detect people in recent Motion images and send Telegram alerts."""

from __future__ import annotations

import argparse
import base64
import configparser
import json
import os
import re
import shlex
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = APP_DIR / "conf_connect_model.conf"
DEFAULT_MOTION_DIR = Path("/var/lib/motion")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_CRON_LOG_PATH = APP_DIR / "logs" / "detection_5min.log"


@dataclass
class ModelConfig:
    endpoint_url: str
    model_name: str
    prompt: str
    user_id: str
    user_pw: str
    timeout_seconds: int


@dataclass
class TelegramConfig:
    token: str
    chat_id: str
    timeout_seconds: int


@dataclass
class AppConfig:
    model: ModelConfig
    telegram: TelegramConfig
    motion_dir: Path
    lookback_minutes: int
    recursive: bool
    event_log_path: Path


def get_config_value(section: configparser.SectionProxy, key: str, default: str = "") -> str:
    value = section.get(key, fallback=default)
    return value.strip() if isinstance(value, str) else str(value).strip()


def get_config_int(section: configparser.SectionProxy, key: str, default: int) -> int:
    try:
        return section.getint(key, fallback=default)
    except ValueError:
        return default


def get_config_bool(section: configparser.SectionProxy, key: str, default: bool) -> bool:
    try:
        return section.getboolean(key, fallback=default)
    except ValueError:
        return default


def load_config(config_path: Path) -> AppConfig:
    if not config_path.exists():
        raise FileNotFoundError(f"configuration file not found: {config_path}")

    parser = configparser.ConfigParser()
    parser.read(config_path, encoding="utf-8")

    model_section = parser["model"] if parser.has_section("model") else parser["DEFAULT"]
    telegram_section = parser["telegram"] if parser.has_section("telegram") else parser["DEFAULT"]
    motion_section = parser["motion"] if parser.has_section("motion") else parser["DEFAULT"]

    endpoint_url = get_config_value(model_section, "endpoint_url", "")
    server_url = get_config_value(model_section, "server_url", "http://127.0.0.1:11434")
    if not endpoint_url:
        endpoint_url = f"{server_url.rstrip('/')}/api/generate"

    telegram_token = get_config_value(telegram_section, "bot_token") or get_config_value(telegram_section, "token")
    telegram_chat_id = get_config_value(telegram_section, "chat_id")
    telegram_token = telegram_token or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat_id = telegram_chat_id or os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    event_log_path = Path(get_config_value(motion_section, "event_log_path", str(APP_DIR / "person_detected_events.jsonl")))
    if not event_log_path.is_absolute():
        event_log_path = (config_path.parent / event_log_path).resolve()

    return AppConfig(
        model=ModelConfig(
            endpoint_url=endpoint_url,
            model_name=get_config_value(model_section, "model_name", "gemma4:31b"),
            prompt=get_config_value(model_section, "prompt"),
            user_id=get_config_value(model_section, "user_id"),
            user_pw=get_config_value(model_section, "user_pw") or get_config_value(model_section, "password"),
            timeout_seconds=get_config_int(model_section, "timeout_seconds", 120),
        ),
        telegram=TelegramConfig(
            token=telegram_token,
            chat_id=telegram_chat_id,
            timeout_seconds=get_config_int(telegram_section, "timeout_seconds", 30),
        ),
        motion_dir=Path(get_config_value(motion_section, "motion_dir", str(DEFAULT_MOTION_DIR))).expanduser(),
        lookback_minutes=get_config_int(motion_section, "lookback_minutes", 5),
        recursive=get_config_bool(motion_section, "recursive", False),
        event_log_path=event_log_path.expanduser(),
    )


def image_modified_at(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime)


def iter_image_files(motion_dir: Path, recursive: bool) -> list[Path]:
    if not motion_dir.exists():
        return []
    if recursive:
        candidates = motion_dir.rglob("*")
    else:
        candidates = motion_dir.iterdir()
    return [path for path in candidates if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS]


def get_recent_images(motion_dir: Path, minutes: int, recursive: bool = False) -> list[Path]:
    cutoff = datetime.now() - timedelta(minutes=max(1, minutes))
    recent_images: list[Path] = []
    for path in iter_image_files(motion_dir, recursive):
        try:
            if image_modified_at(path) >= cutoff:
                recent_images.append(path)
        except OSError as exc:
            print(f"skip unreadable file: {path} ({exc})", file=sys.stderr)
    recent_images.sort(key=image_modified_at)
    return recent_images


def encode_image_base64(image_path: Path) -> str:
    return base64.b64encode(image_path.read_bytes()).decode("ascii")


def get_requests_module() -> Any:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import requests

    return requests


def build_model_headers(config: ModelConfig) -> dict[str, str]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if config.user_id and config.user_pw:
        token = base64.b64encode(f"{config.user_id}:{config.user_pw}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    return headers


def extract_model_text(payload: Any) -> str:
    if isinstance(payload, dict):
        if isinstance(payload.get("response"), str):
            return payload["response"]
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict) and isinstance(message.get("content"), str):
                    return message["content"]
                if isinstance(first.get("text"), str):
                    return first["text"]
        if isinstance(payload.get("content"), str):
            return payload["content"]
    return str(payload)


def detect_person_via_model(image_path: Path, config: ModelConfig) -> str:
    requests_module = get_requests_module()
    image_base64 = encode_image_base64(image_path)
    payload = {
        "model": config.model_name,
        "prompt": config.prompt,
        "images": [image_base64],
        "stream": False,
    }

    timeout_seconds = max(1, config.timeout_seconds)
    print("3. AI 모델 접속 완료", flush=True)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            requests_module.post,
            config.endpoint_url,
            json=payload,
            headers=build_model_headers(config),
            timeout=timeout_seconds,
        )
        started_at = time.monotonic()
        while not future.done():
            elapsed_seconds = int(time.monotonic() - started_at)
            print(f"4. 회신 대기중 (time out : {timeout_seconds}초 / 현재 {elapsed_seconds}초)", flush=True)
            try:
                response = future.result(timeout=1)
                break
            except TimeoutError:
                continue
        else:
            response = future.result()

    response.raise_for_status()
    try:
        return extract_model_text(response.json())
    except ValueError:
        return response.text


def parse_model_response(response_text: str) -> tuple[bool, int]:
    text = response_text.strip()
    if not text:
        return False, 0

    try:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        data = json.loads(match.group(0) if match else text)
        detected = data.get("person_detected", data.get("detected", data.get("person", False)))
        if isinstance(detected, str):
            detected = detected.strip().lower() in {"true", "yes", "y", "1", "person", "detected"}
        count = data.get("person_count", data.get("count", 0))
        count = int(count)
        return bool(detected) and count > 0, max(0, count)
    except (TypeError, ValueError, json.JSONDecodeError):
        pass

    lower_text = text.lower()
    negative_words = ("no", "none", "false", "0명", "없", "존재하지", "감지되지", "보이지 않")
    positive_words = ("yes", "true", "person", "people", "human", "사람", "인원", "명", "존재", "감지")
    numbers = [int(number) for number in re.findall(r"\d+", text)]

    if any(word in lower_text for word in negative_words) and not any(word in lower_text for word in ("yes", "true")):
        return False, 0
    if numbers and numbers[0] > 0:
        return True, numbers[0]
    if any(word in lower_text for word in positive_words):
        return True, 1
    return False, 0


def format_time(value: datetime) -> str:
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def build_detection_event(image_path: Path, person_count: int, model_response: str) -> dict[str, Any]:
    captured_at = image_modified_at(image_path).astimezone()
    detected_at = datetime.now().astimezone()
    return {
        "person_detected": True,
        "person_count": person_count,
        "person_detected_at": format_time(detected_at),
        "image_captured_at": format_time(captured_at),
        "image_mtime_epoch": image_path.stat().st_mtime,
        "image_path": str(image_path),
        "image_name": image_path.name,
        "model_response": model_response.strip(),
    }


def save_detection_event(event_log_path: Path, event: dict[str, Any]) -> None:
    event_log_path.parent.mkdir(parents=True, exist_ok=True)
    with event_log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def send_telegram_photo(config: TelegramConfig, event: dict[str, Any]) -> None:
    requests_module = get_requests_module()
    if not config.token or not config.chat_id:
        raise ValueError("telegram bot_token/chat_id is empty")

    image_path = Path(str(event["image_path"]))
    caption = "\n".join(
        [
            "Motion person detection",
            f"file: {event['image_name']}",
            f"people: {event['person_count']}",
            f"person_detected_at: {event['person_detected_at']}",
            f"image_captured_at: {event['image_captured_at']}",
            f"model: {str(event['model_response'])[:300]}",
        ]
    )
    url = f"https://api.telegram.org/bot{config.token}/sendPhoto"
    with image_path.open("rb") as photo:
        response = requests_module.post(
            url,
            data={"chat_id": config.chat_id, "caption": caption},
            files={"photo": photo},
            timeout=max(1, config.timeout_seconds),
        )
    response.raise_for_status()


def process_recent_images(config: AppConfig, dry_run: bool = False) -> int:
    recent_images = get_recent_images(config.motion_dir, config.lookback_minutes, config.recursive)
    print(f"1. {config.motion_dir} 에서 파일 가져오기 완료", flush=True)
    print(f"motion_dir={config.motion_dir}")
    print(f"lookback_minutes={config.lookback_minutes}")
    print(f"recent_images={len(recent_images)}")

    alerts_sent = 0
    if not recent_images:
        return alerts_sent

    requests_module = get_requests_module()
    for image_path in recent_images:
        print(f"detecting: {image_path}")
        print("2. 수집 파일을 AI 모델에 전송하여 detection 실행", flush=True)
        try:
            model_response = detect_person_via_model(image_path, config.model)
        except requests_module.RequestException as exc:
            print(f"model request failed: {image_path.name}: {exc}", file=sys.stderr)
            continue
        except OSError as exc:
            print(f"image read failed: {image_path.name}: {exc}", file=sys.stderr)
            continue

        detected, person_count = parse_model_response(model_response)
        print("5. 회신 완료, 결과 전송", flush=True)
        print(f"model_response={model_response.strip()}")
        print(f"detected={detected} person_count={person_count}")
        if not detected:
            continue

        event = build_detection_event(image_path, person_count, model_response)
        try:
            save_detection_event(config.event_log_path, event)
        except OSError as exc:
            print(f"event log save failed: {image_path.name}: {exc}", file=sys.stderr)
        else:
            print(f"event saved: {config.event_log_path}")

        if dry_run:
            print(f"dry-run: telegram send skipped for {image_path.name}")
            alerts_sent += 1
            continue

        try:
            send_telegram_photo(config.telegram, event)
        except (requests_module.RequestException, OSError, ValueError) as exc:
            print(f"telegram send failed: {image_path.name}: {exc}", file=sys.stderr)
            continue
        alerts_sent += 1
        print(f"telegram sent: {image_path.name}")

    return alerts_sent


def build_crontab_line(args: argparse.Namespace) -> str:
    python_bin = Path(sys.executable or "/usr/bin/python3").resolve()
    script_path = Path(__file__).resolve()
    config_path = args.config.expanduser()
    log_path = args.cron_log.expanduser()

    command_parts = [
        shlex.quote(str(python_bin)),
        shlex.quote(str(script_path)),
        "--config",
        shlex.quote(str(config_path)),
    ]
    if args.dir is not None:
        command_parts.extend(["--dir", shlex.quote(str(args.dir.expanduser()))])
    if args.minutes is not None:
        command_parts.extend(["--minutes", str(args.minutes)])
    if args.recursive:
        command_parts.append("--recursive")
    if args.dry_run:
        command_parts.append("--dry-run")

    command = " ".join(command_parts)
    return f"*/5 * * * * cd {shlex.quote(str(APP_DIR))} && {command} >> {shlex.quote(str(log_path))} 2>&1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect people in recent Motion images and notify Telegram.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help=f"config path (default: {DEFAULT_CONFIG_PATH})")
    parser.add_argument("--dir", type=Path, help="override motion directory")
    parser.add_argument("--minutes", type=int, help="override lookback minutes")
    parser.add_argument("--recursive", action="store_true", help="scan motion directory recursively")
    parser.add_argument("--dry-run", action="store_true", help="detect only; do not send Telegram messages")
    parser.add_argument("--print-crontab", action="store_true", help="print a crontab line that runs this script every 5 minutes")
    parser.add_argument(
        "--cron-log",
        type=Path,
        default=DEFAULT_CRON_LOG_PATH,
        help=f"log path for --print-crontab output (default: {DEFAULT_CRON_LOG_PATH})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.print_crontab:
        print(build_crontab_line(args))
        return 0

    try:
        config = load_config(args.config)
    except (OSError, configparser.Error) as exc:
        print(f"config load failed: {exc}", file=sys.stderr)
        return 1

    if args.dir is not None:
        config.motion_dir = args.dir.expanduser()
    if args.minutes is not None:
        config.lookback_minutes = args.minutes
    if args.recursive:
        config.recursive = True

    alerts_sent = process_recent_images(config, dry_run=args.dry_run)
    print(f"alerts_sent={alerts_sent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
