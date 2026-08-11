"""Google Cloud Vertex AI backend for llm_routing."""

from .client import GCPVertexClient, GCPConfigError

__all__ = ["GCPVertexClient", "GCPConfigError"]
