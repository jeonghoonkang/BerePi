#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CHECK_DAYS="${1:-}"
ACTION="${2:-}"

if (( $# < 1 || $# > 2 )) || [[ ! ${CHECK_DAYS} =~ ^[1-9][0-9]*$ ]] ||
    [[ -n ${ACTION} && ${ACTION} != "--kill" ]]; then
    echo "사용법: $0 조회할_일수 [--kill]" >&2
    echo "조회만: $0 1" >&2
    echo "조회 후 대상 계정 프로세스 종료: $0 1 --kill" >&2
    exit 1
fi

LOG_DIR="${SCRIPT_DIR}/log"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/run_ssh_login_IP_$(date '+%Y%m%d_%H%M%S').log"
JOURNAL_FILE="$(mktemp)"
SUCCESS_USERS_FILE="$(mktemp)"
trap 'rm -f -- "${JOURNAL_FILE}" "${SUCCESS_USERS_FILE}"' EXIT
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "실행 시각: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "조회 기간: 최근 ${CHECK_DAYS}일"
echo "실행 모드: $([[ ${ACTION} == '--kill' ]] && echo '조회 및 프로세스 종료' || echo '조회 전용')"
echo "로그 파일: ${LOG_FILE}"

sudo -v
sudo journalctl -u ssh --since "${CHECK_DAYS} days ago" --no-pager > "${JOURNAL_FILE}"

echo
echo "SSH 접속 IP별 성공/실패 횟수와 성공 로그인 ID"
printf '%-40s %10s %10s  %s\n' "IP 주소" "성공" "실패" "로그인 ID"
printf '%-40s %10s %10s  %s\n' "----------------------------------------" "----------" "----------" "--------------------"

result="$(awk -v users_file="${SUCCESS_USERS_FILE}" '
    /Accepted|Failed/ {
        status = ($0 ~ /Accepted/) ? "success" : "failed"
        ip = ""; user = ""
        for (i = 1; i < NF; i++) {
            if ($i == "from" && $(i + 1) ~ /^[0-9A-Fa-f:.]+$/) ip = $(i + 1)
            if (status == "success" && $i == "for") {
                user = $(i + 1)
                if (user == "invalid" && $(i + 2) == "user") user = $(i + 3)
            }
        }
        if (ip != "") {
            all_ips[ip] = 1
            if (status == "success") {
                success[ip]++
                if (user ~ /^[A-Za-z_][A-Za-z0-9_.-]*[$]?$/) {
                    key = ip SUBSEP user
                    if (!seen_ip_user[key]) {
                        login_users[ip] = login_users[ip] (login_users[ip] == "" ? "" : ",") user
                        seen_ip_user[key] = 1
                    }
                    if (!seen_user[user]) { print user >> users_file; seen_user[user] = 1 }
                }
            } else failed[ip]++
        }
    }
    END { for (ip in all_ips) printf "%s\t%d\t%d\t%s\n", ip, success[ip] + 0, failed[ip] + 0, login_users[ip] }
' "${JOURNAL_FILE}" | sort -t $'\t' -k1,1)"

if [[ -z ${result} ]]; then
    echo "해당 기간에 SSH 성공 또는 실패 기록이 없습니다."
else
    while IFS=$'\t' read -r ip success_count failed_count login_ids; do
        printf '%-40s %10d %10d  %s\n' "${ip}" "${success_count}" "${failed_count}" "${login_ids:--}"
    done <<< "${result}"
fi

if [[ ! -s ${SUCCESS_USERS_FILE} ]]; then
    echo; echo "성공한 SSH 로그인 ID가 없어 계정별 조사를 종료합니다."
    echo "로그 저장 완료: ${LOG_FILE}"
    exit 0
fi

sort -u -o "${SUCCESS_USERS_FILE}" "${SUCCESS_USERS_FILE}"
CALLER_USER="${SUDO_USER:-$(id -un)}"

while IFS= read -r login_user; do
    [[ -n ${login_user} ]] || continue
    echo; echo "================================================================"
    echo "로그인 ID 조사: ${login_user}"

    if ! passwd_entry="$(getent passwd "${login_user}")" || [[ -z ${passwd_entry} ]]; then
        echo "현재 시스템에 존재하지 않는 계정입니다."
        continue
    fi
    IFS=':' read -r _ _ login_uid _ _ _ _ <<< "${passwd_entry}"
    echo "UID: ${login_uid}"

    echo "[사용자 crontab]"
    if ! sudo crontab -u "${login_user}" -l 2>/dev/null; then echo "등록된 사용자 crontab이 없습니다."; fi

    echo "[시스템 cron에서 해당 ID를 참조하는 항목]"
    system_cron_result="$(sudo awk -v user="${login_user}" '
        /^[[:space:]]*#/ || NF == 0 { next }
        $6 == user { print FILENAME ":" FNR ":" $0 }
    ' /etc/crontab /etc/cron.d/* 2>/dev/null || true)"
    if [[ -n ${system_cron_result} ]]; then echo "${system_cron_result}"; else echo "해당 ID의 시스템 cron 항목이 없습니다."; fi

    echo "[현재 실행 중인 프로세스]"
    process_result="$(ps -U "${login_user}" -u "${login_user}" -o pid=,ppid=,etime=,command= 2>/dev/null || true)"
    if [[ -n ${process_result} ]]; then echo "${process_result}"; else echo "실행 중인 프로세스가 없습니다."; fi

    if [[ ${ACTION} != "--kill" ]]; then
        echo "조회 전용 모드이므로 프로세스를 종료하지 않습니다."
        continue
    fi
    if [[ ${login_user} == "root" || ${login_user} == "${CALLER_USER}" || ${login_uid} -lt 1000 ]]; then
        echo "안전 제외: root, 실행 계정 또는 UID 1000 미만 계정은 종료하지 않습니다."
        continue
    fi
    [[ -n ${process_result} ]] || continue

    echo "프로세스에 SIGTERM을 전송합니다: ${login_user}"
    sudo pkill -TERM -u "${login_uid}" 2>/dev/null || true
    sleep 2
    remaining_pids="$(pgrep -u "${login_uid}" 2>/dev/null || true)"
    if [[ -n ${remaining_pids} ]]; then
        echo "남은 프로세스에 SIGKILL을 전송합니다: ${remaining_pids//$'\n'/, }"
        sudo pkill -KILL -u "${login_uid}" 2>/dev/null || true
    fi
    final_processes="$(pgrep -a -u "${login_uid}" 2>/dev/null || true)"
    if [[ -n ${final_processes} ]]; then
        echo "경고: 종료 후에도 남아 있는 프로세스가 있습니다."; echo "${final_processes}"
    else
        echo "해당 ID의 실행 중인 프로세스를 모두 종료했습니다."
    fi
done < "${SUCCESS_USERS_FILE}"

echo; echo "작업 및 로그 저장 완료: ${LOG_FILE}"
