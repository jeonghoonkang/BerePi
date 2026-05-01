#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
import sys

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from pipeline_common import SUPPORTED_MODEL_OPTIONS, build_user_message, model_supports_tools
from rag_webdav import format_retrieved_contexts, read_local_markdown_files, retrieve_markdown_chunks


def check_installed_models(host: str) -> set[str]:
    import requests

    response = requests.get(f"{host.rstrip('/')}/api/tags", timeout=15)
    response.raise_for_status()
    data = response.json()
    return {
        model.get("name", "").strip()
        for model in data.get("models", [])
        if model.get("name", "").strip()
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify shared WebDAV Markdown RAG prompt wiring for every model.")
    parser.add_argument("--cache-dir", default="workspace/webdav_markdown", help="Local markdown cache directory")
    parser.add_argument("--host", default="", help="Optional Ollama host for installed-model checks")
    parser.add_argument("--question", default="Summarize the markdown notes about backup and restore steps.")
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir).expanduser()
    documents = read_local_markdown_files(cache_dir)
    if not documents:
        print(f"No markdown documents found in cache: {cache_dir}", file=sys.stderr)
        return 1

    contexts = format_retrieved_contexts(retrieve_markdown_chunks(args.question, documents, max_chunks=3))
    if not contexts:
        print("Markdown cache exists but no chunk matched the verification question.", file=sys.stderr)
        return 1

    installed_models: set[str] = set()
    if args.host:
        try:
            installed_models = check_installed_models(args.host)
        except Exception as exc:
            print(f"Ollama installed-model check failed: {exc}", file=sys.stderr)

    print(f"Markdown cache: {cache_dir}")
    print(f"Documents: {len(documents)}")
    print(f"Retrieved contexts: {len(contexts)}")
    print("")

    failures = 0
    for model in SUPPORTED_MODEL_OPTIONS:
        prompt = build_user_message(
            prompt=args.question,
            excel_contexts=[],
            markdown_contexts=contexts,
            allow_tools=model_supports_tools(model),
            workspace_root=Path(args.cache_dir).resolve().parent,
        )
        has_rag = "[Markdown Source]" in prompt
        tool_mode = model_supports_tools(model)
        installed = "yes" if model in installed_models else ("unknown" if not args.host else "no")
        status = "OK" if has_rag else "FAIL"
        if not has_rag:
            failures += 1
        print(
            f"{status} model={model} shared_rag={has_rag} "
            f"tool_mode={tool_mode} installed={installed}"
        )

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
