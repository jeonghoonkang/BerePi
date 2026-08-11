from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class BedrockConfigError(RuntimeError):
    pass


class BedrockClient:
    """Small adapter around the model-independent Bedrock Converse API."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        path = Path(
            config_path
            or os.getenv("LLM_ROUTING_BEDROCK_CONFIG")
            or Path(__file__).with_name("bedrock_settings.json")
        )
        try:
            self.settings = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise BedrockConfigError(f"Bedrock config file not found: {path}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise BedrockConfigError(f"Cannot read Bedrock config {path}: {exc}") from exc

        self.region = str(self.settings.get("region") or "").strip()
        self.model_id = str(self.settings.get("model_id") or "").strip()
        if not self.region or not self.model_id:
            raise BedrockConfigError("Bedrock region and model_id are required.")

    def _client(self, timeout: int):
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise BedrockConfigError("boto3 is required: python -m pip install boto3") from exc

        # Let boto3 use its normal credential chain. Optional environment variable
        # names in the settings file are resolved here without storing secrets in git.
        bearer_env = str(self.settings.get("bearer_token_env") or "").strip()
        if bearer_env and os.getenv(bearer_env):
            os.environ["AWS_BEARER_TOKEN_BEDROCK"] = os.environ[bearer_env]

        kwargs: dict[str, Any] = {
            "region_name": self.region,
            "config": Config(connect_timeout=timeout, read_timeout=timeout, retries={"max_attempts": 3, "mode": "standard"}),
        }
        access_env = str(self.settings.get("access_key_id_env") or "AWS_ACCESS_KEY_ID")
        secret_env = str(self.settings.get("secret_access_key_env") or "AWS_SECRET_ACCESS_KEY")
        session_env = str(self.settings.get("session_token_env") or "AWS_SESSION_TOKEN")
        if os.getenv(access_env) and os.getenv(secret_env):
            kwargs["aws_access_key_id"] = os.environ[access_env]
            kwargs["aws_secret_access_key"] = os.environ[secret_env]
            if os.getenv(session_env):
                kwargs["aws_session_token"] = os.environ[session_env]
        return boto3.client("bedrock-runtime", **kwargs)

    @staticmethod
    def _messages(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        source = payload.get("messages")
        if not isinstance(source, list):
            source = [{"role": "user", "content": str(payload.get("prompt") or "")}]
        messages: list[dict[str, Any]] = []
        system: list[dict[str, str]] = []
        for item in source:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "user")
            content = item.get("content")
            if isinstance(content, list):
                text = "\n".join(str(part.get("text") or "") for part in content if isinstance(part, dict) and part.get("type", "text") == "text")
            else:
                text = str(content or "")
            if role == "system":
                system.append({"text": text})
            elif role in {"user", "assistant"}:
                messages.append({"role": role, "content": [{"text": text}]})
        return messages, system

    def converse(self, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
        messages, system = self._messages(payload)
        request: dict[str, Any] = {"modelId": str(payload.get("model") or self.model_id), "messages": messages}
        if system:
            request["system"] = system
        inference: dict[str, Any] = {}
        mappings = {"max_tokens": "maxTokens", "temperature": "temperature", "top_p": "topP"}
        defaults = self.settings.get("inference_config", {})
        for source_key, target_key in mappings.items():
            value = payload.get(source_key, defaults.get(target_key))
            if value is not None:
                inference[target_key] = value
        if inference:
            request["inferenceConfig"] = inference

        response = self._client(timeout).converse(**request)
        content = response.get("output", {}).get("message", {}).get("content", [])
        text = "".join(str(block.get("text") or "") for block in content if isinstance(block, dict))
        return {"response": text, "raw": response}
