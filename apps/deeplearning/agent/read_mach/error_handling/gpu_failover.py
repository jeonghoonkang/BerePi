"""Retry failed local LLM work on a different GPU routing target."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence, TypeVar


ResultT = TypeVar("ResultT")


@dataclass(frozen=True)
class GPUFailoverAttempt:
    target_id: str
    error_type: str
    error_message: str


class GPUFailoverExhaustedError(RuntimeError):
    """Raised after the same work has failed on every available GPU target."""

    def __init__(self, attempts: Sequence[GPUFailoverAttempt]) -> None:
        self.attempts = tuple(attempts)
        summary = "; ".join(
            f"{item.target_id}: {item.error_type}: {item.error_message}"
            for item in self.attempts
        )
        super().__init__(f"모든 가용 GPU에서 작업이 실패했습니다: {summary}")


def is_retryable_gpu_error(exc: Exception) -> bool:
    """Return whether moving the same request to another GPU can reasonably help."""
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int):
        return status_code >= 500 or status_code in {408, 409, 425, 429}
    return True


def execute_with_gpu_failover(
    target_ids: Sequence[str],
    operation: Callable[[str], ResultT],
    *,
    initial_target_id: str | None = None,
    on_failover: Callable[[GPUFailoverAttempt, str], None] | None = None,
    should_retry: Callable[[Exception], bool] = is_retryable_gpu_error,
) -> ResultT:
    """Run work on one GPU and resend the same work to other GPUs after failure."""
    unique_target_ids = list(dict.fromkeys(str(item) for item in target_ids if str(item)))
    if not unique_target_ids:
        raise ValueError("GPU failover를 실행할 target ID가 없습니다.")

    if initial_target_id and initial_target_id in unique_target_ids:
        start = unique_target_ids.index(initial_target_id)
        ordered_target_ids = unique_target_ids[start:] + unique_target_ids[:start]
    else:
        ordered_target_ids = unique_target_ids

    attempts: list[GPUFailoverAttempt] = []
    for index, target_id in enumerate(ordered_target_ids):
        try:
            return operation(target_id)
        except Exception as exc:  # noqa: BLE001 - target failover must preserve arbitrary work errors
            attempt = GPUFailoverAttempt(
                target_id=target_id,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            attempts.append(attempt)
            if not should_retry(exc):
                raise
            if index + 1 >= len(ordered_target_ids):
                raise GPUFailoverExhaustedError(attempts) from exc
            next_target_id = ordered_target_ids[index + 1]
            if on_failover:
                on_failover(attempt, next_target_id)

    raise GPUFailoverExhaustedError(attempts)
