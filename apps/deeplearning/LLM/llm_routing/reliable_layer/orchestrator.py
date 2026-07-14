from __future__ import annotations
import random, time, uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict
from .config import ReliableLayerConfig
from .errors import ReliableAttemptsExhausted, ReliableDeadlineExceeded, is_retryable, safe_error
from .memory import ExplicitMemoryStore
from .progress import ProgressCallback, ProgressEvent, ignore_progress
from .prompt import memory_request, prepare_payload

RouteCallback = Callable[[Dict[str, Any]], Dict[str, Any]]
@dataclass(frozen=True)
class ReliableResult:
    result: dict[str, Any]
    request_id: str
    attempts: int
    events: list[ProgressEvent]
    audit: dict[str, Any]

class ReliableOrchestrator:
    """Deterministic reliability layer around one existing routing call."""
    def __init__(self, memory_store: ExplicitMemoryStore, config: ReliableLayerConfig | None = None, sleep: Callable[[float], None] = time.sleep) -> None:
        self.memory_store, self.config, self.sleep = memory_store, config or ReliableLayerConfig.from_env(), sleep
    @classmethod
    def with_default_store(cls, app_dir: str | Path) -> "ReliableOrchestrator":
        return cls(ExplicitMemoryStore(Path(app_dir) / "reliable_layer" / "data" / "explicit_memory.sqlite3"))
    def generate(self, payload: dict[str, Any], route_once: RouteCallback, progress: ProgressCallback = ignore_progress) -> ReliableResult:
        request_id = str(payload.get("request_id") or uuid.uuid4().hex)
        user_id = str(payload.get("user_id") or payload.get("client_id") or "").strip()
        events: list[ProgressEvent] = []
        def emit(state: str, message: str, attempt: int = 0, **detail: Any) -> None:
            event = ProgressEvent(request_id, state, message, attempt, detail)
            events.append(event)
            try: progress(event)
            except Exception: pass
        emit("preparing", "요청을 준비하고 있습니다.")
        remember, content = memory_request(payload); memory_id = ""
        if remember:
            if not self.config.memory_enabled: raise ValueError("Explicit memory is disabled.")
            if not user_id: raise ValueError("user_id or client_id is required when remember=true.")
            memory_id = self.memory_store.remember(user_id, content, {"request_id": request_id, "source": "generate_api"})
            emit("memory_saved", "요청한 내용을 기억에 저장했습니다.", memory_id=memory_id)
        use_memory = self.config.memory_enabled and payload.get("use_memory", True) is not False
        memories = self.memory_store.list_for_user(user_id, self.config.max_memories_per_request) if use_memory and user_id else []
        prepared, audit = prepare_payload(payload, memories, self.config.max_memory_chars)
        prepared["request_id"] = request_id
        started, errors = time.monotonic(), []
        for attempt in range(1, self.config.max_attempts + 1):
            if time.monotonic() - started >= self.config.total_deadline_seconds:
                raise ReliableDeadlineExceeded(f"request {request_id} exceeded total deadline")
            emit("dispatching", "후방 LLM에 요청을 전달하고 있습니다.", attempt)
            try:
                result = dict(route_once(dict(prepared))); result.setdefault("ok", True)
                result["reliable"] = {"request_id": request_id, "attempts": attempt, "memory_id": memory_id, "memory_count": audit["memory_count"]}
                emit("completed", "응답이 완료되었습니다.", attempt)
                return ReliableResult(result, request_id, attempt, events, {**audit, "errors": errors})
            except Exception as error:
                errors.append(safe_error(error))
                if not is_retryable(error) or attempt >= self.config.max_attempts:
                    emit("failed", "요청을 완료하지 못했습니다.", attempt, error=safe_error(error))
                    raise ReliableAttemptsExhausted(request_id, attempt, error) from error
                delay = min(self.config.max_backoff_seconds, self.config.base_backoff_seconds * 2 ** (attempt - 1)) * random.uniform(0.8, 1.2)
                remaining = self.config.total_deadline_seconds - (time.monotonic() - started)
                if remaining <= 0: raise ReliableDeadlineExceeded(f"request {request_id} exceeded total deadline") from error
                delay = min(delay, remaining)
                emit("retrying", self.config.retry_message, attempt + 1, retry_after_seconds=round(delay, 3), previous_error=safe_error(error))
                self.sleep(delay)
        raise AssertionError("unreachable")
