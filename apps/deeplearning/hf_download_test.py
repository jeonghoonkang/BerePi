#!/usr/bin/env python3
"""Download a popular Hugging Face model and run a simple test.

This script fetches a model from the Hugging Face Hub (default:
``bert-base-uncased``), stores it under ``apps/deeplearning/models``
and performs a basic masked-word prediction to verify that the model
works correctly.

Examples
--------
Download the default model and run the test::

    python hf_download_test.py

Specify a different model (e.g., a smaller DistilBERT)::

    python hf_download_test.py --model distilbert-base-uncased
"""
from __future__ import annotations

import argparse
from pathlib import Path

from huggingface_hub import snapshot_download
from transformers import AutoModelForMaskedLM, AutoTokenizer, pipeline


DEFAULT_MODEL = "bert-base-uncased"


def download_model(model_name: str = DEFAULT_MODEL) -> Path:
    """Download ``model_name`` into the local ``models`` directory.

    The function skips downloading if the model is already present.
    """
    models_dir = Path(__file__).resolve().parent / "models"
    target_dir = models_dir / model_name
    if not target_dir.exists():
        snapshot_download(
            repo_id=model_name,
            local_dir=target_dir,
            local_dir_use_symlinks=False,
        )
    return target_dir


def run_test(model_dir: Path) -> None:
    """Run a basic fill-mask inference to verify the model."""
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForMaskedLM.from_pretrained(model_dir)
    fill_mask = pipeline("fill-mask", model=model, tokenizer=tokenizer)
    results = fill_mask("The capital of France is [MASK].")[:5]
    for res in results:
        token = res["token_str"].strip()
        score = res["score"]
        sequence = res["sequence"]
        print(f"{token:>12} {score:.4f} {sequence}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and test a Hugging Face model")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Model name or repo id to download (default: %(default)s)",
    )
    args = parser.parse_args()
    model_dir = download_model(args.model)
    run_test(model_dir)


if __name__ == "__main__":  # pragma: no cover - script entry point
    main()
