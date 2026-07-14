from __future__ import annotations
import socket
import urllib.error
from typing import Any

RETRYABLE_HTTP_CODES = {408, 425, 429, 500, 502, 503, 504}
class ReliableLayerError(RuntimeError): pass
class ReliableDeadlineExceeded(ReliableLayerError): pass
class ReliableAttemptsExhausted(ReliableLayerError):
    def __init__(self, request_id: str, attempts: int, last_error: BaseException) -> None:
        super().__init__(f"request {request_id} failed after {attempts} attempts: {last_error}")
        self.request_id, self.attempts, self.last_error = request_id, attempts, last_error

def is_retryable(error: BaseException) -> bool:
    if isinstance(error, urllib.error.HTTPError):
        return error.code in RETRYABLE_HTTP_CODES
    return isinstance(error, (TimeoutError, socket.timeout, urllib.error.URLError, ConnectionError, OSError)) or bool(getattr(error, "retryable", False))

def safe_error(error: BaseException) -> dict[str, Any]:
    code = error.code if isinstance(error, urllib.error.HTTPError) else None
    return {"type": type(error).__name__, "http_status": code, "message": str(error)[:500]}
