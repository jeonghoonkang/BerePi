from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class ReliableLayerConfig:
    max_attempts: int = 3
    base_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 8.0
    total_deadline_seconds: float = 600.0
    memory_enabled: bool = True
    max_memories_per_request: int = 20
    max_memory_chars: int = 4_000
    retry_message: str = "응답이 지연되어 다시 시도하고 있습니다. 조금만 더 기다려 주세요."

    @classmethod
    def from_env(cls) -> "ReliableLayerConfig":
        return cls(
            max_attempts=max(1, int(os.getenv("LLM_RELIABLE_MAX_ATTEMPTS", "3"))),
            base_backoff_seconds=max(0.0, float(os.getenv("LLM_RELIABLE_BASE_BACKOFF", "1"))),
            max_backoff_seconds=max(0.0, float(os.getenv("LLM_RELIABLE_MAX_BACKOFF", "8"))),
            total_deadline_seconds=max(1.0, float(os.getenv("LLM_RELIABLE_TOTAL_DEADLINE", "600"))),
            memory_enabled=os.getenv("LLM_RELIABLE_MEMORY_ENABLED", "true").lower() not in {"0", "false", "no"},
            max_memories_per_request=max(0, int(os.getenv("LLM_RELIABLE_MAX_MEMORIES", "20"))),
            max_memory_chars=max(0, int(os.getenv("LLM_RELIABLE_MAX_MEMORY_CHARS", "4000"))),
            retry_message=os.getenv("LLM_RELIABLE_RETRY_MESSAGE", cls.retry_message),
        )
