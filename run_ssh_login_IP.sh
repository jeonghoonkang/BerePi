#!/usr/bin/env bash

set -euo pipefail

CHECK_DAYS="${1:-}"

if (( $# != 1 )) || [[ ! ${CHECK_DAYS} =~ ^[1-9][0-9]*$ ]]; then
    echo "사용법: $0 조회할_일수" >&2
    echo "예: $0 1 또는 $0 100" >&2
    exit 1
fi

sudo -v

echo "최근 ${CHECK_DAYS}일간 SSH 접속 IP별 성공/실패 횟수"
printf '%-40s %10s %10s\n' "IP 주소" "성공" "실패"
printf '%-40s %10s %10s\n' "----------------------------------------" "----------" "----------"

result="$({
    sudo journalctl -u ssh --since "${CHECK_DAYS} days ago" --no-pager
} | awk '
    /Accepted|Failed/ {
        status = ($0 ~ /Accepted/) ? "success" : "failed"
        ip = ""

        for (i = 1; i < NF; i++) {
            if ($i == "from" && $(i + 1) ~ /^[0-9A-Fa-f:.]+$/) {
                ip = $(i + 1)
                break
            }
        }

        if (ip != "") {
            if (status == "success") {
                success[ip]++
            } else {
                failed[ip]++
            }
            all_ips[ip] = 1
        }
    }
    END {
        for (ip in all_ips) {
            printf "%s\t%d\t%d\n", ip, success[ip] + 0, failed[ip] + 0
        }
    }
' | sort -t $'\t' -k1,1)"

if [[ -z "${result}" ]]; then
    echo "해당 기간에 SSH 성공 또는 실패 기록이 없습니다."
    exit 0
fi

while IFS=$'\t' read -r ip success_count failed_count; do
    printf '%-40s %10d %10d\n' "${ip}" "${success_count}" "${failed_count}"
done <<< "${result}"
