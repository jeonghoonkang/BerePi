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

A Hugging Face token may be required for some models such as Llama.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional

try:
    from huggingface_hub import snapshot_download
except ImportError as exc:  # pragma: no cover - handled at runtime
    raise SystemExit(
        "huggingface_hub package is required. Install with 'pip install huggingface_hub'."
    ) from exc


# Mapping of shorthand names to Hugging Face repositories.
MODEL_REPOS = {
    "gemma": "google/gemma-2b",
    "gemma-7b": "google/gemma-7b",
    "llama": "meta-llama/Meta-Llama-3-8B",
    "llama-7b": "meta-llama/Llama-2-7b-hf",
    "qwen": "Qwen/Qwen-7B",
}


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

    snapshot_download(
        repo_id=repo_id,
        local_dir=target_dir,
        local_dir_use_symlinks=False,
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
