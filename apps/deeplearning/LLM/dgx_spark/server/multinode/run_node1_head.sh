#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=multinode_common.sh
source "${SCRIPT_DIR}/multinode_common.sh"

usage() {
  cat <<EOF
Usage: $(basename "$0") [api-port]

Node 1에서 CX-7/RoCE를 검사하고 2-node Ray head 및 vLLM API를 실행합니다.
Worker가 조인할 때까지 기다린 뒤 API 서버를 시작합니다.

Environment overrides:
  HEAD_IP                    CX-7 Head IP (기본값: 자동 감지)
  IMAGE                      ${IMAGE:-vllm/vllm-openai:gemma4-cu130}
  MODEL                      ${MODEL:-google/gemma-4-31b-it}
  RAY_PORT                   ${RAY_PORT:-6379}
  CLUSTER_SIZE               ${CLUSTER_SIZE:-2}
  PIPELINE_PARALLEL_SIZE     ${PIPELINE_PARALLEL_SIZE:-2}
  TENSOR_PARALLEL_SIZE       ${TENSOR_PARALLEL_SIZE:-1}
  CLUSTER_WAIT_TIMEOUT       ${CLUSTER_WAIT_TIMEOUT:-600} seconds

Example:
  HEAD_IP=192.168.100.10 $(basename "$0") 26000
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi
[[ $# -le 1 ]] || { usage >&2; exit 2; }

API_PORT="${1:-${API_PORT:-26000}}"
RAY_PORT="${RAY_PORT:-6379}"
CLUSTER_SIZE="${CLUSTER_SIZE:-2}"
CLUSTER_WAIT_TIMEOUT="${CLUSTER_WAIT_TIMEOUT:-600}"
IMAGE="${IMAGE:-vllm/vllm-openai:gemma4-cu130}"
MODEL="${MODEL:-google/gemma-4-31b-it}"
PIPELINE_PARALLEL_SIZE="${PIPELINE_PARALLEL_SIZE:-2}"
TENSOR_PARALLEL_SIZE="${TENSOR_PARALLEL_SIZE:-1}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.85}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-8192}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-16}"
HF_CACHE_DIR="${HF_CACHE_DIR:-${HOME}/.cache/huggingface}"
CONTAINER_NAME="${HEAD_CONTAINER_NAME:-dgx-spark-vllm-head}"

validate_port API "$API_PORT"
validate_port Ray "$RAY_PORT"
[[ "$CLUSTER_SIZE" =~ ^[0-9]+$ ]] && (( CLUSTER_SIZE >= 2 )) || die "CLUSTER_SIZE는 2 이상이어야 합니다."
[[ "$CLUSTER_WAIT_TIMEOUT" =~ ^[0-9]+$ ]] && (( CLUSTER_WAIT_TIMEOUT > 0 )) || die "CLUSTER_WAIT_TIMEOUT이 유효하지 않습니다."
[[ "$PIPELINE_PARALLEL_SIZE" =~ ^[0-9]+$ ]] && (( PIPELINE_PARALLEL_SIZE > 0 )) || die "PIPELINE_PARALLEL_SIZE가 유효하지 않습니다."
[[ "$TENSOR_PARALLEL_SIZE" =~ ^[0-9]+$ ]] && (( TENSOR_PARALLEL_SIZE > 0 )) || die "TENSOR_PARALLEL_SIZE가 유효하지 않습니다."

load_hf_token
discover_active_rdma
select_local_endpoint "${HEAD_IP:-}"
prepare_docker
ensure_container_name_available "$CONTAINER_NAME"
docker_tty_args

log "Node 2에서 다음 명령으로 조인하십시오:"
printf '  HEAD_IP=%q %q\n' "$LOCAL_IP" "${SCRIPT_DIR}/join_node2_worker.sh"
log "Ray ${CLUSTER_SIZE}개 노드가 모이면 vLLM API(포트 ${API_PORT})를 시작합니다."

exec "${DOCKER[@]}" run --rm "${DOCKER_TTY_ARGS[@]}" \
  --name "$CONTAINER_NAME" \
  --privileged \
  --gpus all \
  --network host \
  --ipc host \
  --ulimit memlock=-1 \
  --ulimit stack=67108864 \
  --entrypoint /bin/bash \
  -e HF_TOKEN="$HF_TOKEN" \
  -e HEAD_IP="$LOCAL_IP" \
  -e LOCAL_IFACE="$LOCAL_IFACE" \
  -e RAY_PORT \
  -e CLUSTER_SIZE \
  -e CLUSTER_WAIT_TIMEOUT \
  -e MODEL \
  -e API_PORT \
  -e PIPELINE_PARALLEL_SIZE \
  -e TENSOR_PARALLEL_SIZE \
  -e GPU_MEMORY_UTILIZATION \
  -e MAX_MODEL_LEN \
  -e MAX_NUM_SEQS \
  -e NCCL_IB_DISABLE=0 \
  -e NCCL_IB_HCA="=${RDMA_HCA_LIST}" \
  -e NCCL_SOCKET_IFNAME="=${RDMA_IFACE_LIST}" \
  -e GLOO_SOCKET_IFNAME="$LOCAL_IFACE" \
  -v "${HF_CACHE_DIR}:/root/.cache/huggingface" \
  "$IMAGE" -lc '
    set -euo pipefail
    cleanup() { ray stop --force >/dev/null 2>&1 || true; }
    trap cleanup EXIT INT TERM

    ray start --head --node-ip-address="$HEAD_IP" --port="$RAY_PORT"

    elapsed=0
    while (( elapsed < CLUSTER_WAIT_TIMEOUT )); do
      active_nodes="$(python3 -c '\''import ray; ray.init(address="auto", logging_level="ERROR"); print(sum(node["Alive"] for node in ray.nodes())); ray.shutdown()'\'' 2>/dev/null | tail -n 1 || true)"
      active_nodes="${active_nodes:-0}"
      printf "[INFO] Ray active nodes: %s/%s\n" "$active_nodes" "$CLUSTER_SIZE"
      if [[ "$active_nodes" =~ ^[0-9]+$ ]] && (( active_nodes >= CLUSTER_SIZE )); then
        break
      fi
      sleep 5
      elapsed=$((elapsed + 5))
    done

    if (( elapsed >= CLUSTER_WAIT_TIMEOUT )); then
      echo "[ERROR] Worker join timeout (${CLUSTER_WAIT_TIMEOUT}s)." >&2
      exit 1
    fi

    trap - EXIT
    exec vllm serve "$MODEL" \
      --host 0.0.0.0 \
      --port "$API_PORT" \
      --trust-remote-code \
      --distributed-executor-backend ray \
      --pipeline-parallel-size "$PIPELINE_PARALLEL_SIZE" \
      --tensor-parallel-size "$TENSOR_PARALLEL_SIZE" \
      --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
      --max-model-len "$MAX_MODEL_LEN" \
      --max-num-seqs "$MAX_NUM_SEQS" \
      --dtype bfloat16
  '
