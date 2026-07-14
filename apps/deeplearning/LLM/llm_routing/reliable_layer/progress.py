from __future__ import annotations
import datetime as dt
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

@dataclass(frozen=True)
class ProgressEvent:
    request_id: str
    state: str
    message: str
    attempt: int = 0
    detail: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())
    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

ProgressCallback = Callable[[ProgressEvent], None]
def ignore_progress(_: ProgressEvent) -> None:
    """Default callback for synchronous clients."""
