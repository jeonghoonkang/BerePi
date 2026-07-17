#!/usr/bin/env bash

# Shared helpers for the two-node DGX Spark vLLM/Ray launch scripts.

log() {
  printf '[INFO] %s\n' "$*"
}

die() {
  printf '[ERROR] %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "필수 명령을 찾을 수 없습니다: $1"
}

validate_port() {
  local name="$1"
  local value="$2"

  [[ "$value" =~ ^[0-9]+$ ]] && (( value >= 1 && value <= 65535 )) || \
    die "${name} 포트가 유효하지 않습니다: ${value}"
}

load_hf_token() {
  local key_file="${KEY_FILE:-${SCRIPT_DIR}/../hf_key.txt}"

  [[ -f "$key_file" ]] || die "Hugging Face 키 파일을 찾을 수 없습니다: ${key_file}"
  HF_TOKEN="$(tr -d '\r\n ' < "$key_file")"
  [[ -n "$HF_TOKEN" ]] || die "Hugging Face 키 파일이 비어 있습니다: ${key_file}"
  export HF_TOKEN
  log "$(basename "$key_file")에서 Hugging Face 토큰을 로드했습니다."
}

contains_value() {
  local expected="$1"
  shift
  local value

  for value in "$@"; do
    [[ "$value" == "$expected" ]] && return 0
  done
  return 1
}

append_unique() {
  local array_name="$1"
  local value="$2"
  local -n target_array="$array_name"

  contains_value "$value" "${target_array[@]:-}" || target_array+=("$value")
}

discover_active_rdma() {
  local hca
  local net_path
  local netdev
  local status

  require_command ibstat
  require_command ip

  ACTIVE_RDMA_DEVICES=()
  ACTIVE_RDMA_IFACES=()

  while IFS= read -r hca; do
    [[ -n "$hca" ]] || continue
    status="$(ibstat "$hca" 2>/dev/null || true)"

    # DGX Spark CX-7 is RoCE (Link layer: Ethernet), not native InfiniBand.
    if ! awk '
      /State:[[:space:]]+Active/ { active=1 }
      /Physical state:[[:space:]]+LinkUp/ { linkup=1 }
      /Link layer:[[:space:]]+(Ethernet|InfiniBand)/ { layer=1 }
      END { exit !(active && linkup && layer) }
    ' <<< "$status"; then
      continue
    fi

    for net_path in "/sys/class/infiniband/${hca}/device/net/"*; do
      [[ -e "$net_path" ]] || continue
      netdev="${net_path##*/}"

      # A usable cluster interface needs carrier and a globally scoped IPv4.
      ip -o link show dev "$netdev" 2>/dev/null | grep -q 'LOWER_UP' || continue
      ip -o -4 addr show dev "$netdev" scope global 2>/dev/null | grep -q 'inet ' || continue

      append_unique ACTIVE_RDMA_DEVICES "$hca"
      append_unique ACTIVE_RDMA_IFACES "$netdev"
    done
  done < <(ibstat -l 2>/dev/null)

  if (( ${#ACTIVE_RDMA_DEVICES[@]} == 0 || ${#ACTIVE_RDMA_IFACES[@]} == 0 )); then
    ibstat >&2 || true
    die "Active/LinkUp 상태이며 IPv4가 설정된 CX-7 RDMA 인터페이스가 없습니다."
  fi

  RDMA_HCA_LIST="$(IFS=,; printf '%s' "${ACTIVE_RDMA_DEVICES[*]}")"
  RDMA_IFACE_LIST="$(IFS=,; printf '%s' "${ACTIVE_RDMA_IFACES[*]}")"
  export RDMA_HCA_LIST RDMA_IFACE_LIST
  log "유효한 RDMA 장치: ${RDMA_HCA_LIST}"
  log "유효한 CX-7 인터페이스: ${RDMA_IFACE_LIST}"
}

interface_for_ip() {
  local requested_ip="$1"
  local iface
  local cidr

  for iface in "${ACTIVE_RDMA_IFACES[@]}"; do
    while IFS= read -r cidr; do
      [[ "${cidr%%/*}" == "$requested_ip" ]] && {
        printf '%s\n' "$iface"
        return 0
      }
    done < <(ip -o -4 addr show dev "$iface" scope global | awk '{print $4}')
  done
  return 1
}

select_local_endpoint() {
  local requested_ip="${1:-}"
  local iface
  local cidr

  if [[ -n "$requested_ip" ]]; then
    iface="$(interface_for_ip "$requested_ip")" || \
      die "지정한 IP(${requested_ip})가 유효한 CX-7 RDMA 인터페이스에 없습니다."
    LOCAL_IP="$requested_ip"
    LOCAL_IFACE="$iface"
  else
    LOCAL_IFACE="${ACTIVE_RDMA_IFACES[0]}"
    cidr="$(ip -o -4 addr show dev "$LOCAL_IFACE" scope global | awk 'NR == 1 {print $4}')"
    LOCAL_IP="${cidr%%/*}"
  fi

  [[ -n "$LOCAL_IP" && -n "$LOCAL_IFACE" ]] || die "로컬 CX-7 endpoint를 결정하지 못했습니다."
  export LOCAL_IP LOCAL_IFACE
  log "클러스터 endpoint: ${LOCAL_IP} (${LOCAL_IFACE})"
}

select_worker_endpoint() {
  local head_ip="$1"
  local requested_ip="${2:-}"
  local route
  local route_iface
  local route_ip

  if [[ -n "$requested_ip" ]]; then
    select_local_endpoint "$requested_ip"
  else
    route="$(ip -o route get "$head_ip" 2>/dev/null | head -n 1)"
    route_iface="$(awk '{for (i=1; i<=NF; i++) if ($i == "dev") print $(i+1)}' <<< "$route")"
    route_ip="$(awk '{for (i=1; i<=NF; i++) if ($i == "src") print $(i+1)}' <<< "$route")"

    [[ -n "$route_iface" && -n "$route_ip" ]] || \
      die "Head IP(${head_ip})로 가는 경로를 찾지 못했습니다."
    contains_value "$route_iface" "${ACTIVE_RDMA_IFACES[@]}" || \
      die "Head IP 경로(${route_iface})가 유효한 CX-7 인터페이스가 아닙니다."

    LOCAL_IFACE="$route_iface"
    LOCAL_IP="$route_ip"
    export LOCAL_IP LOCAL_IFACE
    log "클러스터 endpoint: ${LOCAL_IP} (${LOCAL_IFACE})"
  fi
}

prepare_docker() {
  require_command docker
  mkdir -p "${HF_CACHE_DIR}"

  if (( EUID == 0 )); then
    DOCKER=(docker)
  else
    require_command sudo
    DOCKER=(sudo docker)
  fi

  "${DOCKER[@]}" info >/dev/null 2>&1 || die "Docker daemon 또는 NVIDIA container runtime을 사용할 수 없습니다."
}

ensure_container_name_available() {
  local container_name="$1"

  if "${DOCKER[@]}" ps -a --format '{{.Names}}' | grep -Fxq "$container_name"; then
    die "동일한 Docker 컨테이너 이름이 이미 존재합니다: ${container_name}"
  fi
}

docker_tty_args() {
  DOCKER_TTY_ARGS=(-i)
  [[ -t 0 && -t 1 ]] && DOCKER_TTY_ARGS+=(-t)
}
