from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable

SUPPORTED_MODEL_OPTIONS = [
    "gemma3:1b",
    "gemma3:4b",
    "gemma3:12b",
    "gemma3:27b",
    "qwen2.5-coder:7b",
    "qwen3-coder:30b",
]

MODEL_MEMORY_GUIDE_GB = {
    "gemma3:1b": 4,
    "gemma3:4b": 8,
    "gemma3:12b": 20,
    "gemma3:27b": 40,
    "qwen2.5-coder:7b": 8,
    "qwen3-coder:30b": 20,
}

MODEL_DEFAULT_TEMPERATURES = {
    "gemma3:1b": 0.7,
    "gemma3:4b": 0.7,
    "gemma3:12b": 0.6,
    "gemma3:27b": 0.5,
    "qwen2.5-coder:7b": 0.2,
    "qwen3-coder:30b": 0.2,
}


def model_supports_tools(model: str) -> bool:
    """Return whether the selected model should use tool calling."""
    return model.startswith("qwen2.5-coder:") or model.startswith("qwen3-coder:")


def build_user_message(
    prompt: str,
    excel_contexts: Iterable[str],
    markdown_contexts: Iterable[str],
    allow_tools: bool,
    workspace_root: Path,
) -> str:
    """Build the final prompt content sent to the model."""
    content_parts = [prompt.strip()]

    normalized_markdown_contexts = [context.strip() for context in markdown_contexts if context.strip()]
    if normalized_markdown_contexts:
        content_parts.append(
            "Relevant markdown context retrieved from the shared WebDAV RAG store is below. "
            "Use it when it helps answer the request, and cite the source file names when useful.\n\n"
            + "\n\n".join(normalized_markdown_contexts)
        )

    normalized_excel_contexts = [context.strip() for context in excel_contexts if context.strip()]
    if normalized_excel_contexts:
        content_parts.append(
            "The user also uploaded Excel data. Use the workbook summaries below when relevant.\n\n"
            + "\n\n".join(normalized_excel_contexts)
        )

    if allow_tools:
        content_parts.append(
            "You may use workspace tools when needed. "
            "If the user asks to download a workspace file, call download_file for that file so the UI can expose a download button. "
            f"The workspace root is: {workspace_root.resolve()}"
        )

    return "\n\n".join(part for part in content_parts if part)


def summarize_tool_calls(tool_calls: list[dict]) -> str:
    """Return a stable summary string for loop detection and diagnostics."""
    summary_parts: list[str] = []
    for tool_call in tool_calls:
        function = tool_call.get("function", {})
        tool_name = str(function.get("name", ""))
        arguments = function.get("arguments", {})
        summary_parts.append(f"{tool_name}:{arguments}")
    return " | ".join(summary_parts)


def tokenize_for_rag(text: str) -> list[str]:
    """Tokenize text for light-weight retrieval scoring."""
    return re.findall(r"[A-Za-z0-9_]{2,}", text.lower())
