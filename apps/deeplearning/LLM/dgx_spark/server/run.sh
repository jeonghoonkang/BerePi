#!/usr/bin/env bash

SCRIPT_VERSION="1.0.0"
echo "[INFO] $(basename "$0") version ${SCRIPT_VERSION}"

# 1. 스크립트의 현재 위치를 기준으로 hf_key.txt 경로 지정
KEY_FILE="$(dirname "$0")/hf_key.txt"


# # 2. 키 파일 존재 여부 검증 및 로드
if [ -f "$KEY_FILE" ]; then
   # 파일에서 토큰을 읽어오고 앞뒤 공백 제거(tr -d)
    export HF_TOKEN=$(cat "$KEY_FILE" | tr -d '\r\n ')
    echo "[INFO] hf_key.txt에서 Hugging Face 토큰을 성공적으로 로드했습니다."
else
    echo "[ERROR] hf_key.txt 파일을 찾을 수 없습니다. (경로: $KEY_FILE)"
    exit 1
fi

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
  -e HF_TOKEN="${HF_TOKEN}" \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  vllm/vllm-openai:gemma4-cu130 \
  google/gemma-4-31b-it \
    --host 0.0.0.0 \
    --port "${PORT}" \
    --trust-remote-code \
    --gpu-memory-utilization 0.85 \
    --max-model-len 8192 \
    --max-num-seqs 16 \
    --dtype bfloat16

 # vllm/vllm-openai:latest \
 # google/gemma-4-26b-a4b-it \

# MSI spark
#sudo  docker run --rm -it   --gpus all   -p 2****:2****   -v ~/.cache/huggingface:/root/.cache/huggingface   vllm/vllm-openai:gemma4-cu130   google/gemma-4-31b-it   --host 0.0.0.0   --port 2*****   --trust-remote-code --max-num-seqs 16 --kv-cache-dtype fp8
