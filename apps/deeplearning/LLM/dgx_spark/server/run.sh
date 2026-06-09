#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<EOF
Usage: $(basename "$0") [port]

Starts vLLM OpenAI-compatible Gemma 4 server.

Examples:
  $(basename "$0")
  $(basename "$0") 26001
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -gt 1 ]]; then
  usage >&2
  exit 2
fi

PORT="${1:-26000}"
if [[ ! "${PORT}" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
  echo "Invalid port: ${PORT}" >&2
  usage >&2
  exit 2
fi

sudo docker run --rm -it \
  --privileged \
  --gpus all \
  --network host \
  --ipc=host \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  vllm/vllm-openai:gemma4-cu130 \
  vllm serve google/gemma-4-31b-it \
    --host 0.0.0.0 \
    --port "${PORT}" \
    --trust-remote-code \
    --gpu-memory-utilization 0.85 \
    --max-model-len 4096
