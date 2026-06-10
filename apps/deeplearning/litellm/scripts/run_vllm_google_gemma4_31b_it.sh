#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

load_env
ensure_python
require_command vllm

MODEL_ID="${GOOGLE_GEMMA4_MODEL_ID:-google/gemma-4-31B-it}"
HOST="${GOOGLE_GEMMA4_VLLM_HOST:-127.0.0.1}"
PORT="${GOOGLE_GEMMA4_VLLM_PORT:-8001}"
SERVED_MODEL_NAME="${GOOGLE_GEMMA4_SERVED_MODEL_NAME:-google/gemma-4-31B-it}"
DTYPE="${GOOGLE_GEMMA4_DTYPE:-${VLLM_DTYPE:-bfloat16}}"
MAX_MODEL_LEN="${GOOGLE_GEMMA4_MAX_MODEL_LEN:-${VLLM_MAX_MODEL_LEN:-8192}}"
GPU_MEMORY_UTILIZATION="${GOOGLE_GEMMA4_GPU_MEMORY_UTILIZATION:-${VLLM_GPU_MEMORY_UTILIZATION:-0.88}}"
TENSOR_PARALLEL_SIZE="${GOOGLE_GEMMA4_TENSOR_PARALLEL_SIZE:-${VLLM_TENSOR_PARALLEL_SIZE:-1}}"
MAX_NUM_SEQS="${GOOGLE_GEMMA4_MAX_NUM_SEQS:-${VLLM_MAX_NUM_SEQS:-4}}"

ensure_port_available "${PORT}" "Google Gemma4 vLLM"

echo "Starting vLLM backend: ${MODEL_ID}"
echo "Endpoint: http://${HOST}:${PORT}/v1"

exec vllm serve "${MODEL_ID}" \
  --served-model-name "${SERVED_MODEL_NAME}" \
  --host "${HOST}" \
  --port "${PORT}" \
  --dtype "${DTYPE}" \
  --max-model-len "${MAX_MODEL_LEN}" \
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION}" \
  --tensor-parallel-size "${TENSOR_PARALLEL_SIZE}" \
  --max-num-seqs "${MAX_NUM_SEQS}" \
  --trust-remote-code \
  --enable-auto-tool-choice \
  --tool-call-parser gemma4 \
  --reasoning-parser gemma4
