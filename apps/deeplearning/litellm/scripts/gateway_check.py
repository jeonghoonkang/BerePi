#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv


APP_DIR = Path(__file__).resolve().parents[1]


def load_master_key() -> str:
    load_dotenv(APP_DIR / ".env")
    api_key = os.getenv("LITELLM_MASTER_KEY", "").strip()
    if api_key and api_key != "sk-change-this-litellm-master-key":
        return api_key

    secret_path = APP_DIR / ".secrets" / "litellm_master_key"
    if secret_path.exists():
        return secret_path.read_text(encoding="utf-8").strip()

    raise SystemExit("LITELLM_MASTER_KEY is required.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check LiteLLM gateway connectivity without starting vLLM backends."
    )
    parser.add_argument("--base-url", default=os.getenv("LITELLM_BASE_URL", "http://127.0.0.1:4000/v1"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    api_key = load_master_key()
    models_url = args.base_url.rstrip("/") + "/models"
    request = urllib.request.Request(
        models_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Gateway check failed: HTTP {exc.code}\n{body}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Gateway check failed: {exc.reason}") from exc

    model_ids = [item.get("id", "") for item in payload.get("data", []) if isinstance(item, dict)]
    print("LiteLLM gateway is reachable.")
    print(f"Models endpoint: {models_url}")
    print("Configured models:")
    for model_id in model_ids:
        print(f"- {model_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
