from __future__ import annotations
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Callable, Dict
from .orchestrator import ReliableOrchestrator
from .progress import ProgressCallback, ignore_progress

HandlerRoute = Callable[[BaseHTTPRequestHandler, Dict[str, Any]], Dict[str, Any]]
def route_reliably(handler: BaseHTTPRequestHandler, payload: dict[str, Any], route_prompt: HandlerRoute, *, app_dir: str | Path,
                   progress: ProgressCallback = ignore_progress, orchestrator: ReliableOrchestrator | None = None) -> dict[str, Any]:
    """Adapter for server_routing.route_prompt without importing the monolith."""
    layer = orchestrator or ReliableOrchestrator.with_default_store(app_dir)
    return layer.generate(payload, lambda prepared: route_prompt(handler, prepared), progress).result
