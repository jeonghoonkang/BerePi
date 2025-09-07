#!/usr/bin/env python3
"""Utility for downloading LLM models.

This module provides a helper function ``download_model`` that fetches
models from the Hugging Face Hub and stores them locally under the
``apps/deeplearning/models`` directory. Other applications can import
this module and call ``download_model`` to obtain a local path to a
model that can be loaded without re-downloading.

Example:
    >>> from model_downloader import download_model
    >>> path = download_model("gemma")
    >>> print(path)

The script can also be used directly from the command line::

    python model_downloader.py --model gemma

If authentication is required, place your Hugging Face token in
``hf_token.txt`` (this directory or the repository root) or set the
``HF_TOKEN`` environment variable.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional


# Mapping of shorthand names to Hugging Face repositories.
MODEL_REPOS = {
    "gemma": "google/gemma-2b",
    "gemma-7b": "google/gemma-7b",
    "gemma-3-270m": "google/gemma-3-270m",
    "gemma-3-4b-it": "google/gemma-3-4b-it",
    "llama": "meta-llama/Meta-Llama-3-8B",
    "llama-7b": "meta-llama/Llama-2-7b-hf",
    "gpt-oss-120b": "openai/gpt-oss-120b",
    "gpt-oss-20b": "openai/gpt-oss-20b",

    "qwen": "Qwen/Qwen-7B",
}


def _read_hf_token() -> Optional[str]:
    """Retrieve Hugging Face token from file or environment."""
    token = os.getenv("HF_TOKEN")
    if token:
        return token.strip()
    token_paths = [
        Path(__file__).resolve().parent / "hf_token.txt",
        Path(__file__).resolve().parents[2] / "hf_token.txt",
    ]
    for path in token_paths:
        if path.is_file():
            return path.read_text().strip()
    return None


def download_model(model: str, base_dir: Optional[os.PathLike[str]] = None) -> Path:
    """Download an LLM model and return the local path.

    Args:
        model: Shorthand name or Hugging Face ``repo_id``.
        base_dir: Base directory in which models are stored. When ``None``
            the default is ``apps/deeplearning/models`` relative to this file.

    Returns:
        Path to the downloaded model directory.
    """
    repo_id = MODEL_REPOS.get(model, model)
    base = (
        Path(base_dir)
        if base_dir is not None
        else Path(__file__).resolve().parent / "models"
    )
    target_dir = base / model
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:  # pragma: no cover - handled at runtime
        raise SystemExit(
            "huggingface_hub package is required. Install with 'pip install huggingface_hub'."
        ) from exc

    token = _read_hf_token()
    snapshot_download(
        repo_id=repo_id,
        local_dir=target_dir,
        local_dir_use_symlinks=False,
        token=token,
    )

    return target_dir


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Download LLM models")
    parser.add_argument(
        "--model",
        required=True,
        help="Model name or Hugging Face repo_id (e.g., 'gemma' or 'google/gemma-7b').",
    )
    parser.add_argument(
        "--base-dir",
        default=None,
        help="Base directory for storing models (defaults to 'apps/deeplearning/models').",
    )
    args = parser.parse_args()
    path = download_model(args.model, args.base_dir)
    print(f"Model downloaded to: {path}")


if __name__ == "__main__":
    _cli()
