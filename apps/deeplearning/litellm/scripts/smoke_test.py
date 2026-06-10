#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


APP_DIR = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a small chat request through LiteLLM.")
    parser.add_argument("--base-url", default=os.getenv("LITELLM_BASE_URL", "http://127.0.0.1:4000/v1"))
    parser.add_argument("--model", default="nvidia/gemma-4-31b-it-nvfp4")
    parser.add_argument("--prompt", default="한 문장으로 현재 모델이 응답 중이라고 말해 주세요.")
    parser.add_argument("--max-tokens", type=int, default=64)
    return parser.parse_args()


def main() -> int:
    load_dotenv(APP_DIR / ".env")
    args = parse_args()
    api_key = os.getenv("LITELLM_MASTER_KEY", "").strip()
    if not api_key or api_key == "sk-change-this-litellm-master-key":
        secret_path = APP_DIR / ".secrets" / "litellm_master_key"
        if secret_path.exists():
            api_key = secret_path.read_text(encoding="utf-8").strip()
    if not api_key:
        raise SystemExit("LITELLM_MASTER_KEY is required.")

    client = OpenAI(base_url=args.base_url, api_key=api_key)
    response = client.chat.completions.create(
        model=args.model,
        messages=[{"role": "user", "content": args.prompt}],
        max_tokens=args.max_tokens,
    )
    print(response.choices[0].message.content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
