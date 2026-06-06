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
import urllib.parse
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = APP_DIR / "conf_connect_model.conf"
DEFAULT_MOTION_DIR = Path("/var/lib/motion")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_CRON_LOG_PATH = APP_DIR / "logs" / "detection_5min.log"
MODEL_FAILURE_ALERT_INTERVAL_SECONDS = 60 * 60


@dataclass
class ModelConfig:
    endpoint_url: str
    result_url: str
    model_name: str
    prompt: str
    user_id: str
    user_pw: str
    timeout_seconds: int
    poll_interval_seconds: float


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
    recent_count_log_path: Path
    model_failure_alert_state_path: Path


def get_config_value(section: configparser.SectionProxy, key: str, default: str = "") -> str:
    value = section.get(key, fallback=default)
    return value.strip() if isinstance(value, str) else str(value).strip()


def get_config_int(section: configparser.SectionProxy, key: str, default: int) -> int:
    try:
        return section.getint(key, fallback=default)
    except ValueError:
        return default


def get_config_float(section: configparser.SectionProxy, key: str, default: float) -> float:
    try:
        return section.getfloat(key, fallback=default)
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
    result_url = get_config_value(model_section, "result_url", "")
    server_url = get_config_value(model_section, "server_url", "http://127.0.0.1:8082")
    if not endpoint_url:
        endpoint_url = f"{server_url.rstrip('/')}/api/enqueue-generate"
    if not result_url:
        result_url = f"{server_url.rstrip('/')}/api/prompt-result"

    telegram_token = get_config_value(telegram_section, "bot_token") or get_config_value(telegram_section, "token")
    telegram_chat_id = get_config_value(telegram_section, "chat_id")
    telegram_token = telegram_token or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat_id = telegram_chat_id or os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    event_log_path = Path(
        get_config_value(motion_section, "event_log_path", str(APP_DIR / "logs" / "person_detected_events.jsonl"))
    )
    if not event_log_path.is_absolute():
        event_log_path = (config_path.parent / event_log_path).resolve()
    recent_count_log_path = Path(
        get_config_value(motion_section, "recent_count_log_path", str(APP_DIR / "logs" / "motion_recent_file_counts.jsonl"))
    )
    if not recent_count_log_path.is_absolute():
        recent_count_log_path = (config_path.parent / recent_count_log_path).resolve()
    model_failure_alert_state_path = event_log_path.with_name("model_failure_alert_state.json")

    return AppConfig(
        model=ModelConfig(
            endpoint_url=endpoint_url,
            result_url=result_url,
            model_name=get_config_value(model_section, "model_name", "gemma4:31b"),
            prompt=get_config_value(model_section, "prompt"),
            user_id=get_config_value(model_section, "user_id"),
            user_pw=get_config_value(model_section, "user_pw") or get_config_value(model_section, "password"),
            timeout_seconds=get_config_int(model_section, "timeout_seconds", 600),
            poll_interval_seconds=max(0.2, get_config_float(model_section, "poll_interval_seconds", 1.0)),
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
        recent_count_log_path=recent_count_log_path.expanduser(),
        model_failure_alert_state_path=model_failure_alert_state_path.expanduser(),
    )


def image_modified_at(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime)


def image_history_key(path: Path) -> str:
    stat = path.stat()
    return f"{path.resolve()}:{stat.st_mtime_ns}:{stat.st_size}"


def iter_motion_files(motion_dir: Path, recursive: bool) -> list[Path]:
    if not motion_dir.exists():
        return []
    if recursive:
        candidates = motion_dir.rglob("*")
    else:
        candidates = motion_dir.iterdir()
    return [path for path in candidates if path.is_file()]


def iter_image_files(motion_dir: Path, recursive: bool) -> list[Path]:
    return [path for path in iter_motion_files(motion_dir, recursive) if path.suffix.lower() in IMAGE_EXTENSIONS]


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


def write_recent_count_log(config: AppConfig, recent_images: list[Path]) -> None:
    motion_files = iter_motion_files(config.motion_dir, config.recursive)
    image_file_count = sum(1 for path in motion_files if path.suffix.lower() in IMAGE_EXTENSIONS)
    payload = {
        "created_at": format_time(datetime.now().astimezone()),
        "motion_dir": str(config.motion_dir),
        "motion_dir_exists": config.motion_dir.exists(),
        "recursive": config.recursive,
        "lookback_minutes": config.lookback_minutes,
        "file_count": len(motion_files),
        "image_file_count": image_file_count,
        "recent_image_count": len(recent_images),
    }
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    print(f"motion_recent_count={line}", flush=True)
    config.recent_count_log_path.parent.mkdir(parents=True, exist_ok=True)
    with config.recent_count_log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(line + "\n")


def get_reference_images(motion_dir: Path, recursive: bool = False) -> list[tuple[str, Path]]:
    image_mtimes: list[tuple[Path, datetime]] = []
    for path in iter_image_files(motion_dir, recursive):
        try:
            image_mtimes.append((path, image_modified_at(path)))
        except OSError as exc:
            print(f"skip unreadable file: {path} ({exc})", file=sys.stderr)
    if not image_mtimes:
        return []

    now = datetime.now()
    targets = [
        ("latest", None),
        ("2min_ago", now - timedelta(minutes=2)),
        ("5min_ago", now - timedelta(minutes=5)),
    ]
    selected: list[tuple[str, Path]] = []
    used_paths: set[Path] = set()
    for label, target_time in targets:
        if target_time is None:
            candidates = sorted(image_mtimes, key=lambda item: item[1], reverse=True)
        else:
            candidates = sorted(image_mtimes, key=lambda item: abs((item[1] - target_time).total_seconds()))
        for candidate, _mtime in candidates:
            if candidate not in used_paths:
                selected.append((label, candidate))
                used_paths.add(candidate)
                break
    return selected


def get_latest_image(motion_dir: Path, recursive: bool = False) -> Path | None:
    reference_images = get_reference_images(motion_dir, recursive)
    for label, image_path in reference_images:
        if label == "latest":
            return image_path
    return None


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
        if isinstance(payload.get("visible_response"), str):
            return payload["visible_response"]
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


def prompt_result_url(config: ModelConfig, job_id: int) -> str:
    separator = "&" if urllib.parse.urlparse(config.result_url).query else "?"
    return f"{config.result_url}{separator}{urllib.parse.urlencode({'id': job_id})}"


def wait_for_model_result(config: ModelConfig, job_id: int, requests_module: Any) -> dict[str, Any]:
    timeout_seconds = max(1, config.timeout_seconds)
    deadline = time.monotonic() + timeout_seconds
    poll_count = 1

    while True:
        elapsed_seconds = int(max(0.0, timeout_seconds - (deadline - time.monotonic())))
        print(
            f"4. queue 결과 대기중 "
            f"(job_id: {job_id} / poll: {poll_count} / time out : {timeout_seconds}초 / 현재 {elapsed_seconds}초)",
            flush=True,
        )
        response = requests_module.get(
            prompt_result_url(config, job_id),
            headers=build_model_headers(config),
            timeout=min(30, timeout_seconds),
        )
        response.raise_for_status()
        data = response.json()
        if data.get("done"):
            if data.get("error"):
                raise RuntimeError(str(data.get("error")))
            return data
        if time.monotonic() >= deadline:
            raise TimeoutError(f"prompt job {job_id} did not finish within {timeout_seconds}s")
        poll_count += 1
        time.sleep(config.poll_interval_seconds)


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
    print("3. AI 모델 queue 접속 완료", flush=True)
    response = requests_module.post(
        config.endpoint_url,
        json=payload,
        headers=build_model_headers(config),
        timeout=min(30, timeout_seconds),
    )
    response.raise_for_status()
    enqueue_data = response.json()
    try:
        job_id = int(enqueue_data.get("prompt_queue_id"))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"queue 응답에 prompt_queue_id가 없습니다: {enqueue_data}") from exc
    print(f"3-1. queue 등록 완료: job_id={job_id}", flush=True)
    result_data = wait_for_model_result(config, job_id, requests_module)
    try:
        return extract_model_text(result_data)
    except ValueError:
        return str(result_data)


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
        "image_history_key": image_history_key(image_path),
        "image_path": str(image_path),
        "image_name": image_path.name,
        "model_response": model_response.strip(),
    }


def build_reference_event(image_path: Path, reference_label: str) -> dict[str, Any]:
    captured_at = image_modified_at(image_path).astimezone()
    reported_at = datetime.now().astimezone()
    return {
        "person_detected": False,
        "person_count": 0,
        "person_detected_at": format_time(reported_at),
        "image_captured_at": format_time(captured_at),
        "image_mtime_epoch": image_path.stat().st_mtime,
        "image_history_key": image_history_key(image_path),
        "image_path": str(image_path),
        "image_name": image_path.name,
        "model_response": "No person detected in scanned images.",
        "reference_label": reference_label,
        "event_type": "reference_image",
    }


def build_forced_send_event(image_path: Path) -> dict[str, Any]:
    captured_at = image_modified_at(image_path).astimezone()
    reported_at = datetime.now().astimezone()
    return {
        "person_detected": False,
        "person_count": 0,
        "person_detected_at": format_time(reported_at),
        "image_captured_at": format_time(captured_at),
        "image_mtime_epoch": image_path.stat().st_mtime,
        "image_history_key": image_history_key(image_path),
        "image_path": str(image_path),
        "image_name": image_path.name,
        "model_response": "Forced single file send; model detection was not run.",
        "reference_label": "forced_send_one",
        "event_type": "forced_send_one",
    }


def load_sent_reference_history(event_log_path: Path) -> set[str]:
    sent_keys: set[str] = set()
    if not event_log_path.exists():
        return sent_keys

    try:
        with event_log_path.open("r", encoding="utf-8") as log_file:
            for line in log_file:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("event_type") != "reference_image" or not event.get("telegram_sent"):
                    continue
                key = event.get("image_history_key")
                if isinstance(key, str) and key:
                    sent_keys.add(key)
    except OSError as exc:
        print(f"event history read failed: {event_log_path}: {exc}", file=sys.stderr)
    return sent_keys


def reference_was_sent(event_log_path: Path, image_path: Path) -> bool:
    try:
        key = image_history_key(image_path)
    except OSError as exc:
        print(f"reference history key failed: {image_path.name}: {exc}", file=sys.stderr)
        return False
    return key in load_sent_reference_history(event_log_path)


def save_detection_event(event_log_path: Path, event: dict[str, Any]) -> None:
    event_log_path.parent.mkdir(parents=True, exist_ok=True)
    with event_log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def send_telegram_photo(config: TelegramConfig, event: dict[str, Any]) -> None:
    requests_module = get_requests_module()
    if not config.token or not config.chat_id:
        raise ValueError("telegram bot_token/chat_id is empty")

    image_path = Path(str(event["image_path"]))
    if event.get("person_detected"):
        title = "Motion person detection"
        people_line = f"people: {event['person_count']}"
    else:
        title = "Motion no person detected reference"
        people_line = "people: 0"

    caption = "\n".join(
        [
            title,
            f"file: {event['image_name']}",
            people_line,
            f"reference: {event.get('reference_label', 'detected')}",
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


def send_telegram_message(config: TelegramConfig, text: str) -> None:
    requests_module = get_requests_module()
    if not config.token or not config.chat_id:
        raise ValueError("telegram bot_token/chat_id is empty")

    url = f"https://api.telegram.org/bot{config.token}/sendMessage"
    response = requests_module.post(
        url,
        data={"chat_id": config.chat_id, "text": text},
        timeout=max(1, config.timeout_seconds),
    )
    response.raise_for_status()


def load_last_model_failure_alert_epoch(state_path: Path) -> float:
    if not state_path.exists():
        return 0.0
    try:
        with state_path.open("r", encoding="utf-8") as state_file:
            data = json.load(state_file)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"model failure alert state read failed: {state_path}: {exc}", file=sys.stderr)
        return 0.0

    try:
        return float(data.get("last_sent_epoch", 0))
    except (TypeError, ValueError):
        return 0.0


def save_model_failure_alert_epoch(state_path: Path, sent_epoch: float) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_sent_epoch": sent_epoch,
        "last_sent_at": format_time(datetime.fromtimestamp(sent_epoch).astimezone()),
    }
    with state_path.open("w", encoding="utf-8") as state_file:
        json.dump(payload, state_file, ensure_ascii=False, sort_keys=True)
        state_file.write("\n")


def notify_model_failure(config: AppConfig, image_path: Path, exc: Exception, dry_run: bool = False) -> bool:
    now_epoch = time.time()
    last_sent_epoch = load_last_model_failure_alert_epoch(config.model_failure_alert_state_path)
    if now_epoch - last_sent_epoch < MODEL_FAILURE_ALERT_INTERVAL_SECONDS:
        print("model failure telegram alert skipped: already sent within 1 hour")
        return False

    text = "\n".join(
        [
            "Motion model run failed",
            f"model: {config.model.model_name}",
            f"endpoint: {config.model.endpoint_url}",
            f"file: {image_path.name}",
            f"time: {format_time(datetime.now().astimezone())}",
            f"error: {str(exc)[:500]}",
        ]
    )
    if dry_run:
        print("dry-run: model failure telegram alert skipped")
        return True

    try:
        send_telegram_message(config.telegram, text)
    except Exception as alert_exc:
        print(f"model failure telegram alert failed: {alert_exc}", file=sys.stderr)
        return False

    try:
        save_model_failure_alert_epoch(config.model_failure_alert_state_path, now_epoch)
    except OSError as state_exc:
        print(f"model failure alert state save failed: {state_exc}", file=sys.stderr)
    print("model failure telegram alert sent")
    return True


def process_recent_images(config: AppConfig, dry_run: bool = False) -> int:
    recent_images = get_recent_images(config.motion_dir, config.lookback_minutes, config.recursive)
    print(f"1. {config.motion_dir} 에서 파일 가져오기 완료", flush=True)
    print(f"motion_dir={config.motion_dir}")
    print(f"lookback_minutes={config.lookback_minutes}")
    print(f"recent_images={len(recent_images)}")
    try:
        write_recent_count_log(config, recent_images)
    except OSError as exc:
        print(f"motion recent count log failed: {exc}", file=sys.stderr)

    alerts_sent = 0
    detected_events = 0
    if not recent_images:
        latest_image = get_latest_image(config.motion_dir, config.recursive)
        print(f"no recent images in lookback; latest_image={latest_image}")
        if latest_image is None:
            return alerts_sent
        if reference_was_sent(config.event_log_path, latest_image):
            print(f"latest fallback already sent; skip duplicate: {latest_image.name}")
            return alerts_sent
        event = build_reference_event(latest_image, "latest_no_recent")
        if dry_run:
            print(f"dry-run: latest fallback send skipped: {latest_image.name}")
            return alerts_sent + 1
        requests_module = get_requests_module()
        try:
            send_telegram_photo(config.telegram, event)
        except (requests_module.RequestException, OSError, ValueError) as exc:
            print(f"latest fallback telegram send failed: {latest_image.name}: {exc}", file=sys.stderr)
            return alerts_sent
        event["telegram_sent"] = True
        try:
            save_detection_event(config.event_log_path, event)
        except OSError as exc:
            print(f"reference history save failed: {latest_image.name}: {exc}", file=sys.stderr)
        print(f"latest fallback telegram sent: {latest_image.name}")
        return alerts_sent + 1

    requests_module = get_requests_module()
    for image_path in recent_images:
        print(f"detecting: {image_path}")
        print("2. 수집 파일을 AI 모델에 전송하여 detection 실행", flush=True)
        try:
            model_response = detect_person_via_model(image_path, config.model)
        except (requests_module.RequestException, RuntimeError, TimeoutError, ValueError) as exc:
            print(f"model request failed: {image_path.name}: {exc}", file=sys.stderr)
            notify_model_failure(config, image_path, exc, dry_run=dry_run)
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

        detected_events += 1
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

    if detected_events == 0:
        reference_images = get_reference_images(config.motion_dir, config.recursive)
        print(f"no person detected; reference_images={len(reference_images)}")
        if not reference_images:
            return alerts_sent
        if requests_module is None and not dry_run:
            requests_module = get_requests_module()
        sent_reference_keys = load_sent_reference_history(config.event_log_path)
        for reference_label, image_path in reference_images:
            event = build_reference_event(image_path, reference_label)
            if event["image_history_key"] in sent_reference_keys:
                print(f"reference already sent; skip duplicate: {reference_label}: {image_path.name}")
                continue
            if dry_run:
                print(f"dry-run: no-detection reference send skipped for {reference_label}: {image_path.name}")
                alerts_sent += 1
                continue
            try:
                send_telegram_photo(config.telegram, event)
            except (requests_module.RequestException, OSError, ValueError) as exc:
                print(f"reference telegram send failed: {image_path.name}: {exc}", file=sys.stderr)
                continue
            event["telegram_sent"] = True
            try:
                save_detection_event(config.event_log_path, event)
            except OSError as exc:
                print(f"reference history save failed: {image_path.name}: {exc}", file=sys.stderr)
            sent_reference_keys.add(str(event["image_history_key"]))
            alerts_sent += 1
            print(f"reference telegram sent: {reference_label}: {image_path.name}")

    return alerts_sent


def resolve_force_send_image(config: AppConfig, force_send_one: str) -> Path | None:
    if force_send_one == "latest":
        return get_latest_image(config.motion_dir, config.recursive)

    image_path = Path(force_send_one).expanduser()
    if not image_path.is_absolute():
        image_path = (config.motion_dir / image_path).resolve()
    return image_path


def send_one_image(config: AppConfig, force_send_one: str, dry_run: bool = False) -> int:
    image_path = resolve_force_send_image(config, force_send_one)
    if image_path is None:
        print(f"force-send-one failed: no image files found in {config.motion_dir}", file=sys.stderr)
        return 0
    if not image_path.exists() or not image_path.is_file():
        print(f"force-send-one failed: file not found: {image_path}", file=sys.stderr)
        return 0
    if image_path.suffix.lower() not in IMAGE_EXTENSIONS:
        print(f"force-send-one failed: unsupported image extension: {image_path}", file=sys.stderr)
        return 0

    event = build_forced_send_event(image_path)
    print(f"force-send-one target: {image_path}")
    if dry_run:
        print(f"dry-run: force-send-one telegram send skipped: {image_path.name}")
        return 1

    requests_module = get_requests_module()
    try:
        send_telegram_photo(config.telegram, event)
    except (requests_module.RequestException, OSError, ValueError) as exc:
        print(f"force-send-one telegram send failed: {image_path.name}: {exc}", file=sys.stderr)
        return 0

    event["telegram_sent"] = True
    try:
        save_detection_event(config.event_log_path, event)
    except OSError as exc:
        print(f"force-send-one history save failed: {image_path.name}: {exc}", file=sys.stderr)
    print(f"force-send-one telegram sent: {image_path.name}")
    return 1


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
    if args.send_one is not None:
        command_parts.append("--send-one")
        if args.send_one != "latest":
            command_parts.append(shlex.quote(str(args.send_one)))

    command = " ".join(command_parts)
    return f"*/5 * * * * cd {shlex.quote(str(APP_DIR))} && {command} >> {shlex.quote(str(log_path))} 2>&1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect people in recent Motion images and notify Telegram.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help=f"config path (default: {DEFAULT_CONFIG_PATH})")
    parser.add_argument("--dir", type=Path, help="override motion directory")
    parser.add_argument("--minutes", type=int, help="override lookback minutes")
    parser.add_argument("--recursive", action="store_true", help="scan motion directory recursively")
    parser.add_argument("--dry-run", action="store_true", help="detect only; do not send Telegram messages")
    parser.add_argument(
        "--send-one",
        nargs="?",
        const="latest",
        metavar="IMAGE_PATH",
        help=(
            "force-send exactly one image via Telegram without model detection. "
            "When IMAGE_PATH is omitted, send the latest image from the motion directory."
        ),
    )
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

    if args.send_one is not None:
        alerts_sent = send_one_image(config, args.send_one, dry_run=args.dry_run)
    else:
        alerts_sent = process_recent_images(config, dry_run=args.dry_run)
    print(f"alerts_sent={alerts_sent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
