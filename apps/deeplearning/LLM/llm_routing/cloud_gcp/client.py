from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class GCPConfigError(RuntimeError):
    pass


class GCPVertexClient:
    """Call a self-deployed Vertex AI Gemma endpoint via Chat Completions."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        path = Path(
            config_path
            or os.getenv("LLM_ROUTING_GCP_CONFIG")
            or Path(__file__).with_name("gcp_settings.json")
        )
        try:
            self.settings = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise GCPConfigError(f"GCP config file not found: {path}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise GCPConfigError(f"Cannot read GCP config {path}: {exc}") from exc

        self.project_id = str(self.settings.get("project_id") or "").strip()
        self.location = str(self.settings.get("location") or "").strip()
        self.endpoint_id = str(self.settings.get("endpoint_id") or "").strip()
        self.model_id = str(self.settings.get("model_id") or "google/gemma-4-31b-it").strip()
        if not self.project_id or not self.location or not self.endpoint_id:
            raise GCPConfigError("GCP project_id, location, and endpoint_id are required.")

    @property
    def endpoint_url(self) -> str:
        configured = str(self.settings.get("endpoint_url") or "").strip()
        if configured:
            return configured
        return (
            f"https://{self.location}-aiplatform.googleapis.com/v1/projects/"
            f"{self.project_id}/locations/{self.location}/endpoints/"
            f"{self.endpoint_id}/chat/completions"
        )

    def _access_token(self) -> str:
        token_env = str(self.settings.get("access_token_env") or "GOOGLE_OAUTH_ACCESS_TOKEN")
        if os.getenv(token_env):
            return str(os.environ[token_env])
        service_account_env = str(
            self.settings.get("service_account_file_env")
            or "GOOGLE_APPLICATION_CREDENTIALS"
        )
        if service_account_env != "GOOGLE_APPLICATION_CREDENTIALS" and os.getenv(service_account_env):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.environ[service_account_env]
        try:
            import google.auth
            from google.auth.transport.requests import Request
        except ImportError as exc:
            raise GCPConfigError(
                "google-auth is required: python -m pip install google-auth"
            ) from exc
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        credentials.refresh(Request())
        if not credentials.token:
            raise GCPConfigError("Could not obtain a Google Cloud access token.")
        return str(credentials.token)

    @staticmethod
    def _messages(payload: dict[str, Any]) -> list[dict[str, str]]:
        source = payload.get("messages")
        if not isinstance(source, list):
            return [{"role": "user", "content": str(payload.get("prompt") or "")}]
        messages: list[dict[str, str]] = []
        for item in source:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, list):
                content = "\n".join(
                    str(part.get("text") or "")
                    for part in content
                    if isinstance(part, dict) and part.get("type", "text") == "text"
                )
            messages.append({
                "role": str(item.get("role") or "user"),
                "content": str(content or ""),
            })
        return messages

    def generate(self, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
        defaults = self.settings.get("inference_config", {})
        body: dict[str, Any] = {
            "model": self.model_id,
            "messages": self._messages(payload),
            "stream": False,
        }
        for key in ("temperature", "max_tokens", "top_p"):
            value = payload.get(key, defaults.get(key))
            if value is not None:
                body[key] = value
        request = urllib.request.Request(
            self.endpoint_url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._access_token()}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Vertex AI returned HTTP {exc.code}: {detail}") from exc
        choices = data.get("choices", [])
        text = ""
        if choices and isinstance(choices[0], dict):
            message = choices[0].get("message", {})
            if isinstance(message, dict):
                text = str(message.get("content") or "")
        return {"response": text, "raw": data}
