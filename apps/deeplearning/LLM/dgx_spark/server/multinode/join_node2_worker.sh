#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=multinode_common.sh
source "${SCRIPT_DIR}/multinode_common.sh"

usage() {
  cat <<EOF
Usage: $(basename "$0") <head-cx7-ip>
   or: HEAD_IP=<head-cx7-ip> $(basename "$0")

Node 2의 CX-7/RoCE 상태와 Head 연결을 검사한 뒤 Ray worker로 조인합니다.

Environment overrides:
  NODE_IP                    Node 2 CX-7 IP (기본값: Head 경로로 자동 감지)
  IMAGE                      ${IMAGE:-vllm/vllm-openai:gemma4-cu130}
  RAY_PORT                   ${RAY_PORT:-6379}
  RAY_JOIN_TIMEOUT           ${RAY_JOIN_TIMEOUT:-300} seconds

Example:
  $(basename "$0") 192.168.100.10
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi
[[ $# -le 1 ]] || { usage >&2; exit 2; }

HEAD_IP="${1:-${HEAD_IP:-}}"
[[ -n "$HEAD_IP" ]] || { usage >&2; exit 2; }

RAY_PORT="${RAY_PORT:-6379}"
RAY_JOIN_TIMEOUT="${RAY_JOIN_TIMEOUT:-300}"
IMAGE="${IMAGE:-vllm/vllm-openai:gemma4-cu130}"
HF_CACHE_DIR="${HF_CACHE_DIR:-${HOME}/.cache/huggingface}"
CONTAINER_NAME="${WORKER_CONTAINER_NAME:-dgx-spark-vllm-worker}"

validate_port Ray "$RAY_PORT"
[[ "$RAY_JOIN_TIMEOUT" =~ ^[0-9]+$ ]] && (( RAY_JOIN_TIMEOUT > 0 )) || die "RAY_JOIN_TIMEOUT이 유효하지 않습니다."

load_hf_token
discover_active_rdma
select_worker_endpoint "$HEAD_IP" "${NODE_IP:-}"

require_command ping
log "CX-7 경로로 Head(${HEAD_IP}) 연결을 검사합니다."
ping -I "$LOCAL_IFACE" -c 3 -W 2 "$HEAD_IP" >/dev/null || \
  die "Head IP(${HEAD_IP})에 CX-7 인터페이스(${LOCAL_IFACE})로 연결할 수 없습니다."

prepare_docker
ensure_container_name_available "$CONTAINER_NAME"
docker_tty_args

log "Node 2를 Ray cluster ${HEAD_IP}:${RAY_PORT}에 조인합니다."
log "이 프로세스는 Worker를 유지하기 위해 foreground에서 실행됩니다."

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
  -e HEAD_IP \
  -e NODE_IP="$LOCAL_IP" \
  -e LOCAL_IFACE="$LOCAL_IFACE" \
  -e RAY_PORT \
  -e RAY_JOIN_TIMEOUT \
  -e NCCL_IB_DISABLE=0 \
  -e NCCL_IB_HCA="=${RDMA_HCA_LIST}" \
  -e NCCL_SOCKET_IFNAME="=${RDMA_IFACE_LIST}" \
  -e GLOO_SOCKET_IFNAME="$LOCAL_IFACE" \
  -v "${HF_CACHE_DIR}:/root/.cache/huggingface" \
  "$IMAGE" -lc '
    set -euo pipefail
    deadline=$((SECONDS + RAY_JOIN_TIMEOUT))
    while (( SECONDS < deadline )); do
      if ray start \
        --address="${HEAD_IP}:${RAY_PORT}" \
        --node-ip-address="$NODE_IP" \
        --block; then
        exit 0
      fi
      echo "[INFO] Ray head를 기다립니다: ${HEAD_IP}:${RAY_PORT}"
      sleep 5
    done
    echo "[ERROR] Ray worker join timeout (${RAY_JOIN_TIMEOUT}s)." >&2
    exit 1
  '
