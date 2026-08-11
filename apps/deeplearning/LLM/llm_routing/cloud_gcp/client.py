from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


class GCPConfigError(RuntimeError):
    pass


class GoogleAIStudioClient:
    """Call the Google AI Studio Gemini API with an API key."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        path = Path(
            config_path
            or os.getenv("LLM_ROUTING_GCP_CONFIG")
            or Path(__file__).with_name("gcp_settings.json")
        )
        try:
            self.settings = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise GCPConfigError(f"Google AI Studio config file not found: {path}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise GCPConfigError(f"Cannot read Google AI Studio config {path}: {exc}") from exc

        self.model_id = str(self.settings.get("model_id") or "gemma-4-31b-it").strip()
        self.api_version = str(self.settings.get("api_version") or "v1beta").strip()
        self.base_url = str(
            self.settings.get("base_url") or "https://generativelanguage.googleapis.com"
        ).rstrip("/")
        if not self.model_id:
            raise GCPConfigError("Google AI Studio model_id is required.")

    @property
    def endpoint_url(self) -> str:
        model = urllib.parse.quote(self.model_id, safe="-._/")
        return f"{self.base_url}/{self.api_version}/models/{model}:generateContent"

    def _api_key(self) -> str:
        # gcp_settings.json is git-ignored, so a literal key is supported for
        # local deployment. An environment variable remains the safer option.
        key = str(self.settings.get("api_key") or "").strip()
        key_env = str(self.settings.get("api_key_env") or "GEMINI_API_KEY").strip()
        key = key or str(os.getenv(key_env) or "").strip()
        if not key or key == "PUT_YOUR_GOOGLE_AI_STUDIO_API_KEY_HERE":
            raise GCPConfigError(
                f"Google AI Studio API key is required. Set api_key or environment variable {key_env}."
            )
        return key

    def configuration_status(self) -> dict[str, Any]:
        """Return non-secret configuration metadata for the management UI."""
        key_env = str(self.settings.get("api_key_env") or "GEMINI_API_KEY").strip()
        literal = str(self.settings.get("api_key") or "").strip()
        literal_configured = bool(
            literal and literal != "PUT_YOUR_GOOGLE_AI_STUDIO_API_KEY_HERE"
        )
        environment_configured = bool(os.getenv(key_env))
        return {
            "configured": literal_configured or environment_configured,
            "model_id": self.model_id,
            "api_version": self.api_version,
            "base_url": self.base_url,
            "key_source": (
                "settings_file" if literal_configured
                else (f"environment:{key_env}" if environment_configured else "not_configured")
            ),
        }

    @staticmethod
    def _text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(
                str(part.get("text") or "")
                for part in content
                if isinstance(part, dict) and part.get("type", "text") == "text"
            )
        return str(content or "")

    @classmethod
    def _contents(cls, payload: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        source = payload.get("messages")
        if not isinstance(source, list):
            return ([{"role": "user", "parts": [{"text": str(payload.get("prompt") or "")}]}], None)
        contents: list[dict[str, Any]] = []
        system_texts: list[str] = []
        for item in source:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "user")
            text = cls._text(item.get("content"))
            if role == "system":
                system_texts.append(text)
            else:
                contents.append({
                    "role": "model" if role == "assistant" else "user",
                    "parts": [{"text": text}],
                })
        system = {"parts": [{"text": "\n".join(system_texts)}]} if system_texts else None
        return contents, system

    def generate(self, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
        contents, system = self._contents(payload)
        defaults = self.settings.get("generation_config", {})
        generation: dict[str, Any] = {}
        mappings = {
            "temperature": "temperature",
            "max_tokens": "maxOutputTokens",
            "top_p": "topP",
            "top_k": "topK",
        }
        for request_key, api_key in mappings.items():
            value = payload.get(request_key, defaults.get(api_key))
            if value is not None:
                generation[api_key] = value
        thinking_level = payload.get("thinking_level", defaults.get("thinkingLevel"))
        if thinking_level is not None:
            normalized_thinking = str(thinking_level).strip().lower()
            if normalized_thinking not in {"minimal", "high"}:
                raise ValueError("thinking_level must be 'minimal' or 'high'.")
            generation["thinkingConfig"] = {"thinkingLevel": normalized_thinking}
        body: dict[str, Any] = {"contents": contents}
        if system:
            body["systemInstruction"] = system
        if generation:
            body["generationConfig"] = generation

        request = urllib.request.Request(
            self.endpoint_url,
            data=json.dumps(body).encode("utf-8"),
            headers={"x-goog-api-key": self._api_key(), "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Google AI Studio returned HTTP {exc.code}: {detail}") from exc

        text_parts: list[str] = []
        candidates = data.get("candidates", [])
        if candidates and isinstance(candidates[0], dict):
            content = candidates[0].get("content", {})
            if isinstance(content, dict):
                text_parts = [
                    str(part.get("text") or "")
                    for part in content.get("parts", [])
                    if isinstance(part, dict)
                ]
        return {"response": "".join(text_parts), "raw": data}


# Backward-compatible name for imports made before the AI Studio migration.
GCPVertexClient = GoogleAIStudioClient
