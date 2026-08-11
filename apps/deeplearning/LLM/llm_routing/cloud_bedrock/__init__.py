"""AWS Bedrock backend for llm_routing."""

from .client import BedrockClient, BedrockConfigError

__all__ = ["BedrockClient", "BedrockConfigError"]
