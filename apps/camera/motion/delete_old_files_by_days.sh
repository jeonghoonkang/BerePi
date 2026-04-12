#!/bin/bash
# Author: github.com/jeonghoonkang

set -u

print_usage() {
    cat <<'EOF'
Usage:
  ./delete_old_files_by_days.sh [DIRECTORY] [DAYS]

Examples:
  ./delete_old_files_by_days.sh
  ./delete_old_files_by_days.sh /var/lib/motion 10

Behavior:
  - Deletes files older than the selected number of days.
  - If no arguments are given, the script prompts for directory and day option.
  - Day options: 1, 10, 20, or custom input.
EOF
}

prompt_directory() {
    local input_dir
    read -r -p "삭제할 대상 디렉토리 경로를 입력하세요: " input_dir
    echo "$input_dir"
}

prompt_days() {
    local choice
    local custom_days

    echo "삭제 기준 보관일을 선택하세요."
    echo "  1) 1일"
    echo "  2) 10일"
    echo "  3) 20일"
    echo "  4) 직접 입력"

    read -r -p "선택 [1-4]: " choice

    case "$choice" in
        1) echo "1" ;;
        2) echo "10" ;;
        3) echo "20" ;;
        4)
            read -r -p "삭제 기준 일수를 숫자로 입력하세요: " custom_days
            echo "$custom_days"
            ;;
        *)
            echo ""
            ;;
    esac
}

validate_days() {
    case "$1" in
        ''|*[!0-9]*)
            return 1
            ;;
        *)
            return 0
            ;;
    esac
}

main() {
    local target_dir="${1:-}"
    local days="${2:-}"
    local match_count
    local confirm

    if [ "${target_dir:-}" = "-h" ] || [ "${target_dir:-}" = "--help" ]; then
        print_usage
        exit 0
    fi

    if [ -z "$target_dir" ]; then
        target_dir="$(prompt_directory)"
    fi

    if [ -z "$days" ]; then
        days="$(prompt_days)"
    fi

    if [ ! -d "$target_dir" ]; then
        echo "오류: 디렉토리가 존재하지 않습니다: $target_dir" >&2
        exit 1
    fi

    if ! validate_days "$days"; then
        echo "오류: 삭제 기준 일수는 숫자여야 합니다: $days" >&2
        exit 1
    fi

    match_count="$(find "$target_dir" -type f -mtime +"$days" -exec printf x \; | wc -c | tr -d ' ')"

    if [ "$match_count" -eq 0 ]; then
        echo "삭제할 파일이 없습니다."
        exit 0
    fi

    echo
    echo "대상 디렉토리: $target_dir"
    echo "삭제 기준: ${days}일 초과된 파일"
    echo "삭제 예정 파일 수: $match_count"
    echo
    echo "삭제 예정 파일 예시 (최대 20개):"
    find "$target_dir" -type f -mtime +"$days" | head -n 20
    echo

    read -r -p "계속 진행하시겠습니까? [y/N]: " confirm
    case "$confirm" in
        y|Y|yes|YES)
            find "$target_dir" -type f -mtime +"$days" -exec rm -f {} +
            echo "삭제가 완료되었습니다."
            ;;
        *)
            echo "삭제를 취소했습니다."
            ;;
    esac
}

main "$@"
