#!/usr/bin/env python3
"""LLM Routing service status and prompt-generation smoke test."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

DEFAULT_URL = "http://keties.iptime.org:4004"
DEFAULT_PROMPT = "연결 테스트입니다. 다른 설명 없이 정확히 OK라고만 답하세요."


class RoutingCheckError(RuntimeError):
    """Raised when the routing service does not pass a smoke-test step."""


@dataclass
class CheckResult:
    ok: bool
    base_url: str
    service_status: str
    model: str
    target_count: int
    target_name: str
    response: str
    status_seconds: float
    generation_seconds: float


def request_json(
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    password: str = "",
    timeout: float = 30,
) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    method = "GET"
    if payload is not None:
        method = "POST"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    if password:
        headers["Authorization"] = f"Bearer {password}"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        raise RoutingCheckError(
            f"{method} {url} returned HTTP {exc.code}: {detail or exc.reason}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RoutingCheckError(f"{method} {url} failed: {exc}") from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RoutingCheckError(f"{method} {url} returned invalid JSON: {raw[:300]!r}") from exc
    if not isinstance(parsed, dict):
        raise RoutingCheckError(f"{method} {url} returned a non-object JSON response")
    return parsed


def join_url(base_url: str, path: str) -> str:
    return urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def extract_answer(data: dict[str, Any]) -> str:
    for key in ("response", "text", "output", "content"):
        value = data.get(key)
        if isinstance(value, str):
            return value.strip()
    message = data.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"].strip()
    return ""


def read_password(explicit: str, password_file: str) -> str:
    if explicit:
        return explicit
    environment_password = os.getenv("LLM_ROUTING_PASSWORD", "").strip()
    if environment_password:
        return environment_password
    if password_file:
        path = Path(password_file).expanduser().resolve()
        if not path.exists():
            raise RoutingCheckError(f"Password file not found: {path}")
        return path.read_text(encoding="utf-8").strip()
    return ""


def check_routing(
    base_url: str,
    *,
    password: str,
    prompt: str = DEFAULT_PROMPT,
    expected: str = "OK",
    timeout: float = 120,
    target_id: str = "",
) -> CheckResult:
    started = time.perf_counter()
    status = request_json(join_url(base_url, "/api/status"), timeout=min(timeout, 30))
    status_seconds = time.perf_counter() - started

    if status.get("ok") is not True:
        raise RoutingCheckError(f"Status API reported failure: {status}")
    service_status = str(status.get("status") or "")
    if service_status.lower() not in {"ready", "ok", "healthy", "running"}:
        raise RoutingCheckError(f"Service is not ready: status={service_status!r}")

    targets = status.get("targets")
    target_count = int(
        status.get("target_count")
        or (len(targets) if isinstance(targets, list) else 0)
    )
    if target_count < 1:
        raise RoutingCheckError("No LLM routing targets are registered")
    if not password:
        raise RoutingCheckError(
            "Generation check needs a password. Set LLM_ROUTING_PASSWORD, "
            "use --password-file, or pass --password."
        )

    payload: dict[str, Any] = {
        "client_id": "llm-routing-smoke-test",
        "prompt": prompt,
        "stream": False,
        "timeout": int(timeout),
    }
    if target_id:
        payload["target_id"] = target_id

    generation_started = time.perf_counter()
    generated = request_json(
        join_url(base_url, "/api/generate"),
        payload=payload,
        password=password,
        timeout=timeout,
    )
    generation_seconds = time.perf_counter() - generation_started
    if generated.get("ok") is not True:
        raise RoutingCheckError(f"Generation API reported failure: {generated}")

    answer = extract_answer(generated)
    if not answer:
        raise RoutingCheckError(f"Generation response has no answer text: {generated}")
    if expected and answer.strip().casefold() != expected.strip().casefold():
        raise RoutingCheckError(
            f"Unexpected model response: expected={expected!r}, actual={answer!r}"
        )

    return CheckResult(
        ok=True,
        base_url=base_url.rstrip("/"),
        service_status=service_status,
        model=str(generated.get("model") or status.get("model") or ""),
        target_count=target_count,
        target_name=str(generated.get("target_name") or ""),
        response=answer,
        status_seconds=round(status_seconds, 3),
        generation_seconds=round(generation_seconds, 3),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check LLM Routing status and run one prompt-generation smoke test."
    )
    parser.add_argument(
        "--url",
        default=os.getenv("LLM_ROUTING_URL", DEFAULT_URL),
        help=f"LLM Routing base URL (default: {DEFAULT_URL}).",
    )
    parser.add_argument(
        "--password",
        default="",
        help="API password. Prefer LLM_ROUTING_PASSWORD or --password-file.",
    )
    parser.add_argument("--password-file", default="", help="UTF-8 file containing the API password.")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="Prompt used by the generation test.")
    parser.add_argument("--expected", default="OK", help="Expected exact response; empty disables comparison.")
    parser.add_argument("--target-id", default="", help="Optional target ID to test.")
    parser.add_argument("--timeout", type=float, default=120, help="Generation timeout in seconds.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        password = read_password(args.password, args.password_file)
        result = check_routing(
            args.url,
            password=password,
            prompt=args.prompt,
            expected=args.expected,
            timeout=max(1, args.timeout),
            target_id=args.target_id,
        )
    except RoutingCheckError as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    else:
        print("[PASS] LLM Routing is working")
        print(f"  URL:        {result.base_url}")
        print(f"  status:     {result.service_status} ({result.status_seconds:.3f}s)")
        print(f"  targets:    {result.target_count}")
        print(f"  target:     {result.target_name or '-'}")
        print(f"  model:      {result.model or '-'}")
        print(f"  generation: {result.generation_seconds:.3f}s")
        print(f"  response:   {result.response}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
