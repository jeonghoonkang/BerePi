#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

load_env
ensure_python
require_command vllm

MODEL_ID="${NVIDIA_GEMMA4_NVFP4_MODEL_ID:-nvidia/Gemma-4-31B-IT-NVFP4}"
HOST="${NVIDIA_GEMMA4_NVFP4_VLLM_HOST:-127.0.0.1}"
PORT="${NVIDIA_GEMMA4_NVFP4_VLLM_PORT:-8002}"
SERVED_MODEL_NAME="${NVIDIA_GEMMA4_NVFP4_SERVED_MODEL_NAME:-nvidia/Gemma-4-31B-IT-NVFP4}"
MAX_MODEL_LEN="${NVIDIA_GEMMA4_NVFP4_MAX_MODEL_LEN:-${VLLM_MAX_MODEL_LEN:-8192}}"
GPU_MEMORY_UTILIZATION="${NVIDIA_GEMMA4_NVFP4_GPU_MEMORY_UTILIZATION:-${VLLM_GPU_MEMORY_UTILIZATION:-0.88}}"
TENSOR_PARALLEL_SIZE="${NVIDIA_GEMMA4_NVFP4_TENSOR_PARALLEL_SIZE:-${VLLM_TENSOR_PARALLEL_SIZE:-1}}"
MAX_NUM_SEQS="${NVIDIA_GEMMA4_NVFP4_MAX_NUM_SEQS:-${VLLM_MAX_NUM_SEQS:-4}}"
QUANTIZATION="${NVIDIA_GEMMA4_NVFP4_QUANTIZATION:-modelopt}"

ensure_port_available "${PORT}" "NVIDIA Gemma4 NVFP4 vLLM"

echo "Starting vLLM backend: ${MODEL_ID}"
echo "Endpoint: http://${HOST}:${PORT}/v1"

exec vllm serve "${MODEL_ID}" \
  --served-model-name "${SERVED_MODEL_NAME}" \
  --host "${HOST}" \
  --port "${PORT}" \
  --max-model-len "${MAX_MODEL_LEN}" \
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION}" \
  --tensor-parallel-size "${TENSOR_PARALLEL_SIZE}" \
  --max-num-seqs "${MAX_NUM_SEQS}" \
  --quantization "${QUANTIZATION}" \
  --trust-remote-code \
  --enable-prefix-caching \
  --enable-auto-tool-choice \
  --tool-call-parser gemma4 \
  --reasoning-parser gemma4
