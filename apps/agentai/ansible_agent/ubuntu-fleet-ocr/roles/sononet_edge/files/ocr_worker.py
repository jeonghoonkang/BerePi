#!/usr/bin/env python3
"""Idempotently OCR Nextcloud-synchronized images through an OpenAI-compatible API."""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import mimetypes
import os
import sqlite3
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


PROMPT_VERSION = "ocr-v1"
PROMPT = (
    "Perform OCR on this image. Transcribe every visible character exactly, including "
    "Korean and English. Preserve reading order and line breaks. Do not summarize, "
    "translate, explain, or invent missing text. Return only the transcription as plain "
    "text. If there is no readable text, return [NO_TEXT]."
)
SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None or not value.strip():
        raise RuntimeError(f"required environment variable is missing: {name}")
    return value.strip()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as target:
        target.write(data)
        target.flush()
        os.fsync(target.fileno())
        temporary = Path(target.name)
    os.replace(temporary, path)


def open_database(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    database = sqlite3.connect(path)
    database.execute("PRAGMA journal_mode=WAL")
    database.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            source_path TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            status TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            error TEXT,
            processed_at TEXT,
            PRIMARY KEY (source_path, sha256, model, prompt_version)
        )
        """
    )
    return database


def already_handled(
    database: sqlite3.Connection, relative_path: str, digest: str, model: str
) -> bool:
    row = database.execute(
        """
        SELECT status FROM jobs
        WHERE source_path=? AND sha256=? AND model=? AND prompt_version=?
        """,
        (relative_path, digest, model, PROMPT_VERSION),
    ).fetchone()
    return bool(row and row[0] in {"success", "skipped_too_large"})


def record_job(
    database: sqlite3.Connection,
    relative_path: str,
    digest: str,
    model: str,
    status: str,
    error: str | None = None,
) -> None:
    database.execute(
        """
        INSERT INTO jobs
            (source_path, sha256, model, prompt_version, status, attempts, error, processed_at)
        VALUES (?, ?, ?, ?, ?, 1, ?, ?)
        ON CONFLICT(source_path, sha256, model, prompt_version) DO UPDATE SET
            status=excluded.status,
            attempts=jobs.attempts + 1,
            error=excluded.error,
            processed_at=excluded.processed_at
        """,
        (relative_path, digest, model, PROMPT_VERSION, status, error, utc_now()),
    )
    database.commit()


def extract_content(response: dict[str, Any]) -> str:
    content = response["choices"][0]["message"]["content"]
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(
            str(item.get("text", ""))
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ).strip()
    raise ValueError("inference response has an unsupported content format")


def request_ocr(path: Path, api_base: str, api_key: str, model: str) -> tuple[str, dict[str, Any]]:
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    image_data = base64.b64encode(path.read_bytes()).decode("ascii")
    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": 4096,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_data}"},
                    },
                ],
            }
        ],
    }
    request = urllib.request.Request(
        f"{api_base.rstrip('/')}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        raw = json.loads(response.read().decode("utf-8"))
    return extract_content(raw), raw


def image_candidates(input_root: Path, stable_age: int) -> list[Path]:
    cutoff = time.time() - stable_age
    candidates = [
        path
        for path in input_root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_SUFFIXES
        and path.stat().st_mtime <= cutoff
    ]
    candidates.sort(key=lambda item: (item.stat().st_mtime, str(item)))
    return candidates


def main() -> int:
    device_id = env("SONONET_DEVICE_ID")
    sync_root = Path(env("NEXTCLOUD_LOCAL_DIR", "/var/lib/sononet/sync"))
    input_root = sync_root / env("OCR_INPUT_SUBDIR", "inbox")
    output_root = sync_root / env("OCR_OUTPUT_SUBDIR", "ocr-results")
    api_base = env("OCR_API_BASE_URL")
    if not (
        api_base.startswith("https://")
        or api_base.startswith("http://127.0.0.1")
        or api_base.startswith("http://localhost")
    ):
        raise RuntimeError("OCR_API_BASE_URL must use HTTPS unless it points to localhost")
    api_key = env("OCR_API_KEY")
    model = env("OCR_MODEL", "google/gemma-4-31B-it")
    maximum = int(env("OCR_MAX_FILES_PER_RUN", "25"))
    max_bytes = int(env("OCR_MAX_FILE_BYTES", "20971520"))
    stable_age = int(env("OCR_STABLE_AGE_SECONDS", "30"))
    database = open_database(Path(env("OCR_STATE_DB", "/var/lib/sononet/ocr-state.sqlite3")))

    input_root.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)
    processed = skipped = failed = attempted = 0

    for image_path in image_candidates(input_root, stable_age):
        relative = image_path.relative_to(input_root)
        digest = sha256_file(image_path)
        if already_handled(database, str(relative), digest, model):
            skipped += 1
            continue
        if attempted >= maximum:
            break
        attempted += 1
        if image_path.stat().st_size > max_bytes:
            record_job(database, str(relative), digest, model, "skipped_too_large")
            print(json.dumps({"event": "ocr_skip_too_large", "path": str(relative)}))
            skipped += 1
            continue

        try:
            text, raw = request_ocr(image_path, api_base, api_key, model)
            result_base = output_root / relative.parent / f"{relative.name}.ocr"
            metadata = {
                "device_id": device_id,
                "source_relative_path": str(relative),
                "source_sha256": digest,
                "source_size_bytes": image_path.stat().st_size,
                "source_mtime": dt.datetime.fromtimestamp(
                    image_path.stat().st_mtime, tz=dt.timezone.utc
                ).isoformat(),
                "model": model,
                "prompt_version": PROMPT_VERSION,
                "processed_at": utc_now(),
                "text": text,
                "usage": raw.get("usage"),
            }
            atomic_write(Path(f"{result_base}.txt"), f"{text}\n")
            atomic_write(
                Path(f"{result_base}.json"),
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            )
            record_job(database, str(relative), digest, model, "success")
            processed += 1
            print(
                json.dumps(
                    {"event": "ocr_success", "path": str(relative), "sha256": digest}
                )
            )
        except (OSError, ValueError, KeyError, urllib.error.URLError) as error:
            message = str(error)[:1000]
            record_job(database, str(relative), digest, model, "failed", message)
            failed += 1
            print(
                json.dumps(
                    {"event": "ocr_failed", "path": str(relative), "error": message}
                ),
                file=sys.stderr,
            )

    print(
        json.dumps(
            {
                "event": "ocr_run_complete",
                "device_id": device_id,
                "processed": processed,
                "skipped": skipped,
                "failed": failed,
            }
        )
    )
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # top-level configuration and database errors
        print(json.dumps({"event": "ocr_fatal", "error": str(error)[:1000]}), file=sys.stderr)
        raise SystemExit(2)
