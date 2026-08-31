#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BLOCK_LIST="${SCRIPT_DIR}/run_secure_block_ip_list.txt"
REVIEW_LIST="${SCRIPT_DIR}/run_secure_review_ip_list.txt"
HOSTS_DENY="/etc/hosts.deny"
CHECK_DAYS=1
DRY_RUN=0
declare -a APPROVED_PRIVATE_IPS=()
declare -a APPROVED_PRIVATE_CIDRS=()

usage() {
    cat <<EOF
사용법: $0 [조회할 일수] [옵션]
       $0 --days 일수 [옵션]

옵션:
  --days N                       최근 N일의 SSH 실패 기록 조회
  --include-private-ip IP        지정한 사설 IP의 차단을 허용 (반복 가능)
  --include-private-cidr CIDR    지정한 사설 CIDR의 차단을 허용 (반복 가능)
  --dry-run                      파일과 시스템을 변경하지 않고 예상 작업만 출력
  -h, --help                     도움말 출력
EOF
}

while (( $# > 0 )); do
    case "$1" in
        --days)
            [[ $# -ge 2 ]] || { echo "오류: --days 값이 필요합니다." >&2; exit 1; }
            CHECK_DAYS=$2
            shift 2
            ;;
        --include-private-ip)
            [[ $# -ge 2 ]] || { echo "오류: --include-private-ip 값이 필요합니다." >&2; exit 1; }
            APPROVED_PRIVATE_IPS+=("$2")
            shift 2
            ;;
        --include-private-cidr)
            [[ $# -ge 2 ]] || { echo "오류: --include-private-cidr 값이 필요합니다." >&2; exit 1; }
            APPROVED_PRIVATE_CIDRS+=("$2")
            shift 2
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        [1-9]|[1-9][0-9]*)
            CHECK_DAYS=$1
            shift
            ;;
        *)
            echo "오류: 알 수 없는 인자입니다: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if [[ ! ${CHECK_DAYS} =~ ^[1-9][0-9]*$ ]]; then
    echo "오류: 조회 일수는 1 이상의 정수여야 합니다: ${CHECK_DAYS}" >&2
    exit 1
fi

if [[ ! -f "${BLOCK_LIST}" ]]; then
    echo "오류: IP 목록 파일을 찾을 수 없습니다: ${BLOCK_LIST}" >&2
    exit 1
fi

LOG_DIR="${SCRIPT_DIR}/log"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/run_secure_$(date '+%Y%m%d_%H%M%S').log"
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "실행 시각: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "로그 파일: ${LOG_FILE}"

is_valid_ipv4() {
    local ip=$1
    local -a octets
    local octet

    IFS='.' read -r -a octets <<< "${ip}"
    [[ ${#octets[@]} -eq 4 ]] || return 1

    for octet in "${octets[@]}"; do
        [[ ${octet} =~ ^[0-9]{1,3}$ ]] || return 1
        (( 10#${octet} <= 255 )) || return 1
    done
}

ipv4_to_int() {
    local ip=$1
    local a b c d
    IFS='.' read -r a b c d <<< "${ip}"
    printf '%u' "$(( (10#${a} << 24) + (10#${b} << 16) + (10#${c} << 8) + 10#${d} ))"
}

is_valid_cidr() {
    local cidr=$1
    local network prefix
    [[ ${cidr} == */* ]] || return 1
    network=${cidr%/*}
    prefix=${cidr#*/}
    is_valid_ipv4 "${network}" || return 1
    [[ ${prefix} =~ ^[0-9]{1,2}$ ]] || return 1
    (( 10#${prefix} >= 0 && 10#${prefix} <= 32 ))
}

cidr_contains() {
    local ip=$1
    local cidr=$2
    local network=${cidr%/*}
    local prefix=${cidr#*/}
    local ip_int network_int mask

    ip_int=$(ipv4_to_int "${ip}")
    network_int=$(ipv4_to_int "${network}")
    if (( prefix == 0 )); then
        mask=0
    else
        mask=$(( (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF ))
    fi
    (( (ip_int & mask) == (network_int & mask) ))
}

is_private_ipv4() {
    local ip=$1
    cidr_contains "${ip}" "10.0.0.0/8" ||
        cidr_contains "${ip}" "172.16.0.0/12" ||
        cidr_contains "${ip}" "192.168.0.0/16"
}

is_private_cidr() {
    local cidr=$1
    local network=${cidr%/*}
    local prefix=${cidr#*/}
    if cidr_contains "${network}" "10.0.0.0/8" && (( prefix >= 8 )); then
        return 0
    fi
    if cidr_contains "${network}" "172.16.0.0/12" && (( prefix >= 12 )); then
        return 0
    fi
    if cidr_contains "${network}" "192.168.0.0/16" && (( prefix >= 16 )); then
        return 0
    fi
    return 1
}

is_approved_private_ip() {
    local ip=$1
    local approved
    for approved in "${APPROVED_PRIVATE_IPS[@]}"; do
        [[ ${ip} == "${approved}" ]] && return 0
    done
    for approved in "${APPROVED_PRIVATE_CIDRS[@]}"; do
        cidr_contains "${ip}" "${approved}" && return 0
    done
    return 1
}

declare -A PROTECTED_IPS=()
register_protected_ip() {
    local ip=$1
    is_valid_ipv4 "${ip}" && PROTECTED_IPS["${ip}"]=1
}

for local_ip in $(hostname -I 2>/dev/null || true); do
    register_protected_ip "${local_ip}"
done
if [[ -n ${SSH_CONNECTION:-} ]]; then
    read -r ssh_client_ip _ <<< "${SSH_CONNECTION}"
    register_protected_ip "${ssh_client_ip}"
fi

is_protected_ip() {
    [[ -n ${PROTECTED_IPS[$1]+x} ]]
}

for approved_ip in "${APPROVED_PRIVATE_IPS[@]}"; do
    if ! is_valid_ipv4 "${approved_ip}" || ! is_private_ipv4 "${approved_ip}"; then
        echo "오류: 승인 IP는 유효한 RFC1918 사설 IPv4 주소여야 합니다: ${approved_ip}" >&2
        exit 1
    fi
done
for approved_cidr in "${APPROVED_PRIVATE_CIDRS[@]}"; do
    if ! is_valid_cidr "${approved_cidr}"; then
        echo "오류: 올바르지 않은 승인 CIDR입니다: ${approved_cidr}" >&2
        exit 1
    fi
    if ! is_private_cidr "${approved_cidr}"; then
        echo "오류: 승인 CIDR은 RFC1918 사설망 내부여야 합니다: ${approved_cidr}" >&2
        exit 1
    fi
done

review_private_ip() {
    local ip=$1
    local failed_count=$2
    local detected_at
    detected_at=$(date '+%Y-%m-%d %H:%M:%S %Z')

    if (( DRY_RUN != 0 )); then
        echo "DRY-RUN 검토 보류: ${ip} (${failed_count}회, 사설 IP)"
        return
    fi
    touch "${REVIEW_LIST}"
    if awk -F '|' -v target="${ip}" '{ value=$1; gsub(/^[[:space:]]+|[[:space:]]+$/, "", value); if (value == target) found=1 } END { exit(found ? 0 : 1) }' "${REVIEW_LIST}"; then
        echo "검토 목록에 이미 있음: ${ip} (${failed_count}회)"
    else
        printf '%s | Failed %s회 | %s | private/review\n' "${ip}" "${failed_count}" "${detected_at}" >> "${REVIEW_LIST}"
        echo "검토 보류: ${ip} (${failed_count}회, 사설 IP)"
    fi
}

is_valid_block_pattern() {
    local pattern=$1
    local -a octets
    local octet
    local wildcard_seen=0
    local numeric_octets=0

    if [[ ${pattern} != *'*' ]]; then
        is_valid_ipv4 "${pattern}"
        return
    fi

    IFS='.' read -r -a octets <<< "${pattern}"
    [[ ${#octets[@]} -eq 4 ]] || return 1

    for octet in "${octets[@]}"; do
        if [[ ${octet} == '*' ]]; then
            wildcard_seen=1
        else
            # *가 나온 뒤에는 숫자 옥텟을 다시 사용할 수 없습니다.
            (( wildcard_seen == 0 )) || return 1
            [[ ${octet} =~ ^[0-9]{1,3}$ ]] || return 1
            (( 10#${octet} <= 255 )) || return 1
            (( numeric_octets += 1 ))
        fi
    done

    # 모든 IPv4 주소 차단은 명시적인 방화벽 규칙으로 설정하도록 제외합니다.
    if (( numeric_octets == 0 )); then
        return 1
    fi
}

block_pattern_prefix_bits() {
    local pattern=$1
    local -a octets
    local bits=0
    if [[ ${pattern} != *'*' ]]; then
        printf '32'
        return
    fi
    IFS='.' read -r -a octets <<< "${pattern}"
    for octet in "${octets[@]}"; do
        [[ ${octet} != '*' ]] || break
        (( bits += 8 ))
    done
    printf '%s' "${bits}"
}

block_pattern_sample_ip() {
    local pattern=$1
    printf '%s' "${pattern//\*/0}"
}

block_pattern_contains_ip() {
    local pattern=$1
    local target_ip=$2
    if [[ ${pattern} == *'*' ]]; then
        local prefix=${pattern%%\**}
        [[ ${target_ip} == "${prefix}"* ]]
    else
        [[ ${target_ip} == "${pattern}" ]]
    fi
}

is_private_block_pattern() {
    local pattern=$1
    local sample
    sample=$(block_pattern_sample_ip "${pattern}")
    is_private_ipv4 "${sample}" ||
        block_pattern_contains_ip "${pattern}" "10.0.0.1" ||
        block_pattern_contains_ip "${pattern}" "172.16.0.1" ||
        block_pattern_contains_ip "${pattern}" "192.168.0.1"
}

is_approved_private_pattern() {
    local pattern=$1
    local sample pattern_bits approved approved_bits
    if [[ ${pattern} != *'*' ]]; then
        is_approved_private_ip "${pattern}"
        return
    fi
    sample=$(block_pattern_sample_ip "${pattern}")
    pattern_bits=$(block_pattern_prefix_bits "${pattern}")
    for approved in "${APPROVED_PRIVATE_CIDRS[@]}"; do
        approved_bits=${approved#*/}
        if (( approved_bits <= pattern_bits )) && cidr_contains "${sample}" "${approved}"; then
            return 0
        fi
    done
    return 1
}

block_pattern_is_protected() {
    local pattern=$1
    local protected_ip
    for protected_ip in "${!PROTECTED_IPS[@]}"; do
        block_pattern_contains_ip "${pattern}" "${protected_ip}" && return 0
    done
    return 1
}

to_hosts_deny_pattern() {
    local pattern=$1
    local -a octets
    local octet
    local prefix=''

    if [[ ${pattern} == *'*' ]]; then
        # hosts.deny는 끝에 점이 있는 주소를 네트워크 접두사로 처리합니다.
        IFS='.' read -r -a octets <<< "${pattern}"
        for octet in "${octets[@]}"; do
            [[ ${octet} != '*' ]] || break
            prefix+="${octet}."
        done
        printf '%s' "${prefix}"
    else
        printf '%s' "${pattern}"
    fi
}

sudo -v
if (( DRY_RUN != 0 )); then
    echo "DRY-RUN: 차단 목록, 검토 목록, ${HOSTS_DENY}를 변경하지 않습니다."
fi

echo "최근 ${CHECK_DAYS}일간의 SSH 접속 공격 기록입니다."
echo "------------------------------------------------------------"
if ! sudo journalctl -u ssh --since "${CHECK_DAYS} days ago" --no-pager | grep --color=never "Failed"; then
    echo "해당 기간에 'Failed' SSH 기록이 없습니다."
fi
echo "------------------------------------------------------------"

echo "최근 ${CHECK_DAYS}일간 Failed 기록이 10회 이상인 IP를 확인합니다."
auto_add_date="$(date '+%Y-%m-%d')"
while read -r failed_count failed_ip; do
    [[ -n "${failed_ip:-}" ]] || continue

    if ! is_valid_ipv4 "${failed_ip}"; then
        echo "로그에서 올바르지 않은 IPv4 주소를 건너뜁니다: ${failed_ip}" >&2
        continue
    fi

    if is_protected_ip "${failed_ip}"; then
        echo "보호 대상이라 건너뜀: ${failed_ip} (현재 SSH 접속 또는 서버 자체 IP)"
        continue
    fi

    if is_private_ipv4 "${failed_ip}" && ! is_approved_private_ip "${failed_ip}"; then
        review_private_ip "${failed_ip}" "${failed_count}"
        continue
    fi

    if awk -v target="${failed_ip}" '
        {
            sub(/#.*/, "")
            if ($1 == target) {
                found = 1
            }
        }
        END { exit(found ? 0 : 1) }
    ' "${BLOCK_LIST}"; then
        echo "자동 차단 목록에 이미 있음: ${failed_ip} (${failed_count}회)"
    else
        auto_entry="${failed_ip} # 자동 추가: ${auto_add_date}, 최근 ${CHECK_DAYS}일 Failed ${failed_count}회"
        if (( DRY_RUN != 0 )); then
            echo "DRY-RUN 자동 차단 예정: ${failed_ip} (${failed_count}회)"
        else
            printf '%s\n' "${auto_entry}" >> "${BLOCK_LIST}"
            echo "자동 차단 목록에 추가됨: ${failed_ip} (${failed_count}회)"
        fi
    fi
done < <(
    sudo journalctl -u ssh --since "${CHECK_DAYS} days ago" --no-pager |
        awk '
            /Failed/ {
                for (i = 1; i < NF; i++) {
                    if ($i == "from" && $(i + 1) ~ /^([0-9]{1,3}\.){3}[0-9]{1,3}$/) {
                        print $(i + 1)
                        break
                    }
                }
            }
        ' |
        sort |
        uniq -c |
        awk '$1 >= 10 { print $1, $2 }'
)

declare -a block_ips=()
declare -A seen_ips=()

while IFS= read -r line || [[ -n "${line}" ]]; do
    line=${line%%#*}
    line=${line//$'\r'/}
    read -r ip _ <<< "${line}"
    [[ -n "${ip:-}" ]] || continue

    if ! is_valid_block_pattern "${ip}"; then
        echo "오류: 올바르지 않은 IPv4 주소 또는 차단 패턴입니다: ${ip}" >&2
        echo "와일드카드는 뒤쪽 옥텟부터 연속해서 사용해야 합니다. 예: 154.217.251.* 또는 154.217.*.*" >&2
        exit 1
    fi

    if block_pattern_is_protected "${ip}"; then
        echo "보호 대상과 겹쳐 차단에서 제외: ${ip}"
        continue
    fi

    if is_private_block_pattern "${ip}" && ! is_approved_private_pattern "${ip}"; then
        echo "승인되지 않은 사설 IP/대역이라 차단에서 제외: ${ip}"
        continue
    fi

    if [[ -z "${seen_ips[${ip}]+x}" ]]; then
        block_ips+=("${ip}")
        seen_ips["${ip}"]=1
    fi
done < "${BLOCK_LIST}"

if [[ ${#block_ips[@]} -eq 0 ]]; then
    echo "적용할 수 있는 차단 IP가 없습니다."
    exit 0
fi

if (( DRY_RUN != 0 )); then
    echo "DRY-RUN: 다음 항목을 ${HOSTS_DENY}에 적용할 예정입니다."
    for ip in "${block_ips[@]}"; do
        echo "  sshd: $(to_hosts_deny_pattern "${ip}")"
    done
    exit 0
fi

sudo touch "${HOSTS_DENY}"

for ip in "${block_ips[@]}"; do
    deny_entry="sshd: $(to_hosts_deny_pattern "${ip}")"
    if sudo grep -Fqx -- "${deny_entry}" "${HOSTS_DENY}"; then
        echo "이미 설정됨: ${deny_entry}"
    else
        echo "${deny_entry}" | sudo tee -a "${HOSTS_DENY}" > /dev/null
        echo "추가됨: ${deny_entry}"
    fi
done

echo "차단 설정을 검증합니다."
missing=0
for ip in "${block_ips[@]}"; do
    deny_entry="sshd: $(to_hosts_deny_pattern "${ip}")"
    if sudo grep -Fqx -- "${deny_entry}" "${HOSTS_DENY}"; then
        echo "확인됨: ${deny_entry}"
    else
        echo "누락됨: ${deny_entry}" >&2
        missing=1
    fi
done

if (( missing != 0 )); then
    echo "오류: 일부 IP 주소가 ${HOSTS_DENY}에 설정되지 않았습니다." >&2
    exit 1
fi

echo "완료: run_secure_block_ip_list.txt의 모든 IP 주소가 sshd 차단 목록에 설정되었습니다."

host_name="$(hostname 2>/dev/null || echo '확인 불가')"
host_ips="$(hostname -I 2>/dev/null | xargs || true)"
if [[ -z ${host_ips} ]] && command -v ip > /dev/null 2>&1; then
    host_ips="$(ip -o addr show scope global 2>/dev/null | awk '{ print $4 }' | cut -d/ -f1 | xargs || true)"
fi
host_ips="${host_ips:-확인 불가}"
execution_time="$(date '+%Y-%m-%d %H:%M:%S %Z')"

if hosts_deny_mtime="$(sudo stat -c '%y' "${HOSTS_DENY}" 2>/dev/null)"; then
    :
elif hosts_deny_mtime="$(sudo stat -f '%Sm' -t '%Y-%m-%d %H:%M:%S %Z' "${HOSTS_DENY}" 2>/dev/null)"; then
    :
else
    hosts_deny_mtime="확인 불가"
fi

audit_entry="# 실행 기록 | 호스트명: ${host_name} | IP: ${host_ips} | 실행시간: ${execution_time} | ${HOSTS_DENY} 최종수정: ${hosts_deny_mtime}"
FIDELITY_LOG="${LOG_DIR}/deny_file_fidelity_log.txt"
printf '%s\n' "${audit_entry}" >> "${FIDELITY_LOG}"
echo "별도 이력 로그에 실행 기록을 저장했습니다: ${FIDELITY_LOG}"

echo "IP 차단 목록의 Git 변경 사항을 확인합니다."
if ! command -v git > /dev/null 2>&1; then
    echo "오류: git 명령을 찾을 수 없어 차단 목록을 커밋·푸시하지 못했습니다." >&2
    exit 1
fi

if ! git_repo_root="$(git -C "${SCRIPT_DIR}" rev-parse --show-toplevel 2>/dev/null)"; then
    echo "오류: ${SCRIPT_DIR}가 Git 저장소에 포함되어 있지 않습니다." >&2
    exit 1
fi

block_list_relative="$(git -C "${git_repo_root}" ls-files --full-name "${BLOCK_LIST}")"
if [[ -z ${block_list_relative} ]]; then
    echo "오류: 차단 목록이 Git에서 추적되고 있지 않습니다: ${BLOCK_LIST}" >&2
    exit 1
fi

if git -C "${git_repo_root}" diff --quiet HEAD -- "${block_list_relative}"; then
    echo "차단 목록에 변경이 없어 커밋·푸시를 건너뜁니다."
else
    current_branch="$(git -C "${git_repo_root}" branch --show-current)"
    if [[ -z ${current_branch} ]]; then
        echo "오류: 분리된 HEAD 상태에서는 자동 푸시할 수 없습니다." >&2
        exit 1
    fi

    commit_date="$(date '+%Y-%m-%d')"
    git -C "${git_repo_root}" add -- "${block_list_relative}"
    git -C "${git_repo_root}" -c commit.gpgsign=false commit --only \
        -m "SSH 자동 차단 IP 목록 갱신 ${commit_date}" -- "${block_list_relative}"
    git -C "${git_repo_root}" push -u origin "${current_branch}"
    echo "차단 목록 커밋·푸시 완료: ${current_branch}"
fi
