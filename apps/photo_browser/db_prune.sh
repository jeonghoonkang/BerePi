#!/usr/bin/env bash
# Run from any directory. The Python CLI performs all validation and deletion.
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
CLI="$SCRIPT_DIR/cli.py"
DB=${DB:-${PHOTO_BROWSER_DB:-"$SCRIPT_DIR/db"}}
PLAN=${PLAN:-/var/tmp/photo-db-prune.sqlite}
PYTHON=${PYTHON:-python3}
ACTION=run
LIMIT=1000
UNDER=media
RESUME=0
STOPPED=0
STOP_TIMEOUT=120

usage() {
    cat <<'HELP'
사용법: bash db_prune.sh [run|plan|status|apply] [옵션]
  run                 계획 생성(기존 계획이면 재사용), 결과 표시, 확인 후 삭제 (기본)
  plan                검사·계획만 생성, 삭제하지 않음
  status              기존 계획 결과만 표시, 서버 실행 중에도 사용 가능
  apply               기존 계획 결과 표시, 확인 후 미처리 후보 삭제
  --db PATH           운영 DB 경로 (기본: 스크립트 옆 db, DB 환경변수 지원)
  --plan PATH         SQLite 계획 경로 (기본: /var/tmp/photo-db-prune.sqlite)
  --max-files N       이번 검사/삭제 한도 (기본: 1000)
  --all               이번 검사/삭제 개수 제한 해제
  --under PATH        검사할 DB 상대 경로 (기본: media)
  --resume            기존 계획의 검사를 이어서 진행 (run/plan만, 삭제 시작 전)
  --server-stopped    내장 서버 확인·정상 종료 허용 질문 생략
  --server-stop-timeout N  서버 종료 대기 초 (기본: 120)
  -h, --help          도움말
환경변수: DB, PHOTO_BROWSER_DB, PLAN, PYTHON (Python 실행 파일 경로 하나)
삭제 전에는 출력된 plan_id를 직접 입력해야 합니다. 실제 사진은 삭제하지 않습니다.
HELP
}

fail() { printf '오류: %s\n' "$*" >&2; exit 1; }
if [[ $# -gt 0 ]]; then
    case "$1" in run|plan|status|apply) ACTION=$1; shift ;; esac
fi
while [[ $# -gt 0 ]]; do
    case "$1" in
        --db|--plan|--max-files|--under|--server-stop-timeout)
            [[ $# -ge 2 && -n "$2" ]] || fail "$1 값이 필요합니다."
            case "$1" in
                --db) DB=$2 ;; --plan) PLAN=$2 ;;
                --max-files) LIMIT=$2 ;; --under) UNDER=$2 ;;
                --server-stop-timeout) STOP_TIMEOUT=$2 ;;
            esac
            shift 2 ;;
        --all) LIMIT=all; shift ;;
        --resume) RESUME=1; shift ;;
        --server-stopped) STOPPED=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) fail "알 수 없는 인자: $1 (--help 참고)" ;;
    esac
done
if [[ "$LIMIT" != all ]]; then
    [[ "$LIMIT" =~ ^[1-9][0-9]{0,9}$ ]] || fail '--max-files는 1~1000000000 정수입니다.'
    (( LIMIT <= 1000000000 )) || fail '--max-files는 1000000000 이하여야 합니다.'
fi
[[ "$STOP_TIMEOUT" =~ ^[1-9][0-9]{0,4}$ ]] || fail '--server-stop-timeout은 1~86400 정수입니다.'
(( STOP_TIMEOUT <= 86400 )) || fail '--server-stop-timeout은 86400 이하여야 합니다.'
if (( RESUME )) && [[ "$ACTION" != run && "$ACTION" != plan ]]; then
    fail '--resume은 run 또는 plan에서만 사용할 수 있습니다.'
fi
command -v "$PYTHON" >/dev/null || fail 'Python을 찾지 못했습니다. PYTHON 환경변수를 지정하세요.'
LIMIT_ARGS=()
[[ "$LIMIT" == all ]] || LIMIT_ARGS=(--max-files "$LIMIT")
trap 'printf "\n중단했습니다. 같은 계획의 status로 진행 상황을 확인하세요.\n" >&2; exit 130' INT

# Partial plans/applies deliberately return 2; errors/interrupts must stop the flow.
CLI_STATUS=0
run_cli() {
    local rc=0
    "$PYTHON" "$CLI" "$@" || rc=$?
    if [[ $rc -ne 0 && $rc -ne 2 ]]; then exit "$rc"; fi
    CLI_STATUS=$rc
}
show_status() { run_cli db-prune-status --plan "$PLAN"; }
if [[ "$ACTION" == status ]]; then
    show_status
    exit "$CLI_STATUS"
fi

printf 'DB: %s\n계획: %s\n실행: %s · 이번 개수 한도: %s\n' "$DB" "$PLAN" "$ACTION" "$LIMIT"
if (( ! STOPPED )); then
    printf '대상 DB의 내장 서버를 확인하고 작업 중지·저장 후 정상 종료합니다. 허용하면 yes를 입력하세요. 다른 CLI 작업은 직접 종료하세요.\n'
    answer=''
    if ! read -r -p '서버 자동 종료 허용: ' answer || [[ "$answer" != yes ]]; then
        printf '취소했습니다. 변경하지 않았습니다.\n'; exit 0
    fi
fi

if [[ "$ACTION" == plan || "$ACTION" == run ]]; then
    if [[ "$ACTION" == run && -e "$PLAN" && $RESUME -eq 0 ]]; then
        printf '기존 계획을 재사용합니다. 검사 추가는 --resume, 새 범위 검사는 새 --plan 경로를 사용하세요.\n'
    else
        RESUME_ARGS=()
        (( ! RESUME )) || RESUME_ARGS=(--resume)
        run_cli --db "$DB" db-prune-plan --plan "$PLAN" --server-stopped --server-stop-timeout "$STOP_TIMEOUT" \
            --under "$UNDER" "${LIMIT_ARGS[@]}" "${RESUME_ARGS[@]}"
        if [[ "$ACTION" == plan ]]; then exit "$CLI_STATUS"; fi
    fi
fi

status_json=$(show_status)
printf '%s\n' "$status_json"
# Parse JSON as data; never execute the suggested shell command in a report.
plan_id=$(printf '%s\n' "$status_json" | "$PYTHON" -c '
import json, sys
from pathlib import Path
data = json.load(sys.stdin)
if Path(data["db"]).resolve() != Path(sys.argv[1]).expanduser().resolve():
    sys.exit("오류: 계획의 DB와 지정한 DB가 다릅니다. --db 경로를 확인하세요.")
print(data["plan_id"])
' "$DB")
pending=$(printf '%s\n' "$status_json" | "$PYTHON" -c '
import json, sys
c = json.load(sys.stdin)["counts"]
print(sum(c.get(k, {}).get("files", 0) for k in ("pending", "deleting")))
')
if [[ "$pending" == 0 ]]; then
    printf '이 계획에 미처리 삭제 후보가 없습니다. 추가 검사는 삭제 전 --resume 또는 새 계획으로 실행하세요.\n'
    exit 0
fi
printf '\n미처리 후보: %s개 (이번 처리 한도: %s). 위 counts와 보존 사유를 확인하세요.\n' "$pending" "$LIMIT"
printf '검증된 과거 JSON을 영구 삭제합니다. 원본·managed 사진과 현재 DB 청크는 유지합니다.\n'
printf '삭제하려면 계획 ID를 그대로 입력하세요: %s\n' "$plan_id"
answer=''
if ! read -r -p '삭제 확인 plan_id (Enter: 취소): ' answer || [[ "$answer" != "$plan_id" ]]; then
    printf '삭제를 취소했습니다. 검사 계획은 보존됩니다.\n'; exit 0
fi
run_cli --db "$DB" db-prune-apply --plan "$PLAN" --server-stopped --server-stop-timeout "$STOP_TIMEOUT" \
    --confirm "$plan_id" "${LIMIT_ARGS[@]}"
apply_status=$CLI_STATUS
show_status
printf '현재 계획의 미처리 후보는 같은 명령 또는 apply로 이어서 처리할 수 있습니다.\n'
printf '삭제를 시작한 계획에 검사를 추가할 수 없습니다. 나머지 범위는 새 --plan 경로를 사용하세요.\n'
exit "$apply_status"
