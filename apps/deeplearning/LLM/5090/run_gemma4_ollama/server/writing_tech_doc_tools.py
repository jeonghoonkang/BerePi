#!/usr/bin/env python3
"""Safe adapter for the workshot WebDAV Markdown command-line tools."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ToolValidationError(ValueError):
    """Raised when a caller supplies an unsupported tool argument."""


class ToolUnavailableError(RuntimeError):
    """Raised when the configured CLI or configuration file is unavailable."""


@dataclass(frozen=True)
class ToolInvocation:
    name: str
    argv: list[str]
    stdin_text: str | None = None


def _default_cli_path(server_dir: Path) -> Path:
    override = os.environ.get("WRITING_TECH_DOC_CLI", "").strip()
    if override:
        return Path(override).expanduser()

    for ancestor in (server_dir, *server_dir.parents):
        candidate = ancestor / "workshot" / "agent" / "writing_tech_doc" / "webdav_enhance.py"
        if candidate.is_file():
            return candidate
    return server_dir / "writing_tech_doc" / "webdav_enhance.py"


def _positive_int(value: Any, field: str, *, maximum: int) -> int:
    if isinstance(value, bool):
        raise ToolValidationError(f"{field} must be an integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ToolValidationError(f"{field} must be an integer") from exc
    if not 1 <= number <= maximum:
        raise ToolValidationError(f"{field} must be between 1 and {maximum}")
    return number


def _clean_text(value: Any, field: str, *, maximum: int, multiline: bool = True) -> str:
    text = str(value or "").strip()
    if not text:
        raise ToolValidationError(f"{field} is required")
    if "\x00" in text:
        raise ToolValidationError(f"{field} contains a NUL character")
    if not multiline and any(character in text for character in "\r\n"):
        raise ToolValidationError(f"{field} must be a single line")
    if len(text) > maximum:
        raise ToolValidationError(f"{field} is longer than {maximum} characters")
    return text


class WritingTechDocToolRunner:
    """Validate tool calls and execute the existing workshot CLI without a shell."""

    def __init__(
        self,
        cli_path: Path,
        config_path: Path,
        *,
        python_executable: str = sys.executable,
        timeout_seconds: int = 900,
        max_output_chars: int = 200_000,
        enabled: bool = True,
    ):
        self.cli_path = cli_path.expanduser().resolve()
        self.config_path = config_path.expanduser().resolve()
        self.python_executable = python_executable
        self.timeout_seconds = timeout_seconds
        self.max_output_chars = max_output_chars
        self.enabled = enabled
        self._execution_lock = threading.Lock()

    @classmethod
    def from_environment(cls, server_dir: Path | None = None) -> "WritingTechDocToolRunner":
        root = (server_dir or Path(__file__).resolve().parent).resolve()
        cli_path = _default_cli_path(root)
        config_setting = os.environ.get("WRITING_TECH_DOC_CONFIG", "").strip()
        config_path = Path(config_setting).expanduser() if config_setting else cli_path.with_name("this_config.conf")
        python_executable = os.environ.get("WRITING_TECH_DOC_PYTHON", sys.executable).strip() or sys.executable
        timeout_seconds = _positive_int(
            os.environ.get("WRITING_TECH_DOC_TIMEOUT_SECONDS", "900"),
            "WRITING_TECH_DOC_TIMEOUT_SECONDS",
            maximum=86_400,
        )
        max_output_chars = _positive_int(
            os.environ.get("WRITING_TECH_DOC_MAX_OUTPUT_CHARS", "200000"),
            "WRITING_TECH_DOC_MAX_OUTPUT_CHARS",
            maximum=5_000_000,
        )
        enabled = os.environ.get("WRITING_TECH_DOC_TOOLS_ENABLED", "1").strip().casefold() not in {
            "0", "false", "no", "off",
        }
        return cls(
            cli_path,
            config_path,
            python_executable=python_executable,
            timeout_seconds=timeout_seconds,
            max_output_chars=max_output_chars,
            enabled=enabled,
        )

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "available": self.enabled and self.cli_path.is_file() and self.config_path.is_file(),
            "cli_path": str(self.cli_path),
            "cli_exists": self.cli_path.is_file(),
            "config_path": str(self.config_path),
            "config_exists": self.config_path.is_file(),
            "python_executable": self.python_executable,
            "timeout_seconds": self.timeout_seconds,
            "max_output_chars": self.max_output_chars,
        }

    @staticmethod
    def catalog() -> list[dict[str, Any]]:
        """Return function schemas suitable for an agent or function-calling client."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "boost",
                    "description": "WebDAV Markdown 원본을 기술 문서로 보강합니다.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file": {"type": "string", "description": "선택적인 원격 Markdown 파일명"},
                            "dry_run": {"type": "boolean", "description": "업로드 없이 대상과 변경 유형만 확인"},
                        },
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list",
                    "description": "allom 메모와 boost 입력·출력 파일의 WebDAV 경로를 조회합니다.",
                    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "allom",
                    "description": "메모를 timestamp 기반 memo_alloc Markdown 파일로 WebDAV에 저장합니다. room과 author를 함께 지정하면 개인별 Telegram 경로와 메타데이터를 저장합니다.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "저장할 메모 본문"},
                            "room": {"type": "string", "description": "Telegram 채팅방 ID"},
                            "topic": {"type": "string", "description": "Telegram 토픽 ID. 생략 시 0"},
                            "author": {"type": "string", "description": "Telegram 작성자 ID"},
                            "author_name": {"type": "string", "description": "Telegram 작성자 표시명 또는 사용자명"},
                        },
                        "required": ["content"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "findm",
                    "description": "allom 메모와 boost 원본에서 관련 문장과 단어를 검색합니다.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "검색할 문장 또는 단어"},
                            "page_size": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 1000,
                                "description": "페이지당 결과 수",
                            },
                            "author": {"type": "string", "description": "Telegram 작성자 ID 필터"},
                            "room": {"type": "string", "description": "Telegram 채팅방 ID 필터"},
                            "topic": {"type": "string", "description": "Telegram 토픽 ID 필터"},
                        },
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                },
            },
        ]

    def prepare(self, payload: dict[str, Any]) -> ToolInvocation:
        if not isinstance(payload, dict):
            raise ToolValidationError("tool payload must be a JSON object")
        raw_name = str(payload.get("tool") or payload.get("name") or "").strip().casefold()
        name = "list" if raw_name == "ls" else raw_name
        common_fields = {"tool", "name", "user_id", "username", "password"}
        tool_fields = {
            "boost": {"file", "dry_run"},
            "list": set(),
            "allom": {"content", "room", "topic", "author", "author_name"},
            "findm": {"query", "page_size", "author", "room", "topic"},
        }
        allowed_fields = common_fields | tool_fields.get(name, set())
        unknown_fields = sorted(set(payload) - allowed_fields)
        if unknown_fields:
            raise ToolValidationError("unsupported fields: " + ", ".join(unknown_fields))
        base = [
            self.python_executable,
            str(self.cli_path),
            "--config",
            str(self.config_path),
        ]

        if name == "boost":
            argv = [*base, "boost"]
            dry_run = payload.get("dry_run")
            if dry_run is True:
                argv.append("--dry-run")
            elif dry_run is not None and dry_run is not False:
                raise ToolValidationError("dry_run must be a boolean")
            file_value = payload.get("file")
            if file_value is not None and file_value != "":
                filename = _clean_text(file_value, "file", maximum=255, multiline=False)
                argv.extend(["--file", filename])
            return ToolInvocation(name, argv)

        if name == "list":
            return ToolInvocation(name, [*base, "list"])

        if name == "allom":
            content = _clean_text(payload.get("content"), "content", maximum=1_000_000)
            argv = [*base, "allom"]
            for field, option, maximum in (
                ("room", "--room", 128),
                ("topic", "--topic", 128),
                ("author", "--author", 128),
                ("author_name", "--author-name", 256),
            ):
                value = payload.get(field)
                if value is not None and value != "":
                    clean_value = _clean_text(value, field, maximum=maximum, multiline=False)
                    argv.append(f"{option}={clean_value}")
            return ToolInvocation(name, argv, stdin_text=content)

        if name == "findm":
            query = _clean_text(payload.get("query"), "query", maximum=2_000)
            argv = [*base, "findm", "--no-pager"]
            page_size_value = payload.get("page_size")
            if page_size_value is not None and page_size_value != "":
                page_size = _positive_int(page_size_value, "page_size", maximum=1000)
                argv.extend(["--page-size", str(page_size)])
            for field, option in (("author", "--author"), ("room", "--room"), ("topic", "--topic")):
                value = payload.get(field)
                if value is not None and value != "":
                    clean_value = _clean_text(value, field, maximum=128, multiline=False)
                    argv.append(f"{option}={clean_value}")
            argv.extend(["--", query])
            return ToolInvocation(name, argv)

        raise ToolValidationError("tool must be one of: boost, list, ls, allom, findm")

    def _ensure_available(self) -> None:
        if not self.enabled:
            raise ToolUnavailableError("writing-tech-doc tools are disabled")
        if not self.cli_path.is_file():
            raise ToolUnavailableError(f"writing-tech-doc CLI not found: {self.cli_path}")
        if not self.config_path.is_file():
            raise ToolUnavailableError(f"writing-tech-doc config not found: {self.config_path}")

    def _truncate(self, text: str) -> tuple[str, bool]:
        if len(text) <= self.max_output_chars:
            return text, False
        omitted = len(text) - self.max_output_chars
        return text[: self.max_output_chars] + f"\n...[{omitted} characters omitted]", True

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_available()
        invocation = self.prepare(payload)
        started = time.monotonic()
        try:
            with self._execution_lock:
                completed = subprocess.run(
                    invocation.argv,
                    cwd=str(self.cli_path.parent),
                    input=invocation.stdin_text,
                    text=True,
                    capture_output=True,
                    timeout=self.timeout_seconds,
                    check=False,
                )
        except subprocess.TimeoutExpired as exc:
            raise ToolUnavailableError(
                f"{invocation.name} exceeded the {self.timeout_seconds}s timeout"
            ) from exc
        stdout, stdout_truncated = self._truncate(completed.stdout or "")
        stderr, stderr_truncated = self._truncate(completed.stderr or "")
        return {
            "ok": completed.returncode == 0,
            "tool": invocation.name,
            "returncode": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "output_truncated": stdout_truncated or stderr_truncated,
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
