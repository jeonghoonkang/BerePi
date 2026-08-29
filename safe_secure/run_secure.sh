#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BLOCK_LIST="${SCRIPT_DIR}/run_secure_block_ip_list.txt"
HOSTS_DENY="/etc/hosts.deny"
CHECK_DAYS="${1:-1}"

if (( $# > 1 )) || [[ ! ${CHECK_DAYS} =~ ^[1-9][0-9]*$ ]]; then
    echo "사용법: $0 [조회할_일수]" >&2
    echo "예: $0 1, $0 2, $0 100" >&2
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

sudo -v

echo "최근 ${CHECK_DAYS}일간의 SSH 접속 공격 기록입니다."
echo "------------------------------------------------------------"
if ! sudo journalctl -u ssh --since "${CHECK_DAYS} days ago" --no-pager | grep --color=never "Failed"; then
    echo "해당 기간에 'Failed' SSH 기록이 없습니다."
fi
echo "------------------------------------------------------------"

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

echo "최근 ${CHECK_DAYS}일간 Failed 기록이 10회 이상인 IP를 확인합니다."
auto_add_date="$(date '+%Y-%m-%d')"
while read -r failed_count failed_ip; do
    [[ -n "${failed_ip:-}" ]] || continue

    if ! is_valid_ipv4 "${failed_ip}"; then
        echo "로그에서 올바르지 않은 IPv4 주소를 건너뜁니다: ${failed_ip}" >&2
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
        echo "${auto_entry}" | tee -a "${BLOCK_LIST}" > /dev/null
        echo "자동 차단 목록에 추가됨: ${failed_ip} (${failed_count}회)"
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

    if [[ -z "${seen_ips[${ip}]+x}" ]]; then
        block_ips+=("${ip}")
        seen_ips["${ip}"]=1
    fi
done < "${BLOCK_LIST}"

if [[ ${#block_ips[@]} -eq 0 ]]; then
    echo "오류: ${BLOCK_LIST}에 차단할 IP 주소가 없습니다." >&2
    exit 1
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
