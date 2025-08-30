#!/bin/bash

HOME=""
# 로그 파일 경로를 안전하게 설정합니다.
LOG="$HOME/cron_pironman5.log"
echo $LOG

# 로그 파일이 존재하지 않으면, 디렉터리를 만들고 빈 파일을 생성합니다.
if [ ! -f "$LOG" ]; then
    mkdir -p "$(dirname "$LOG")"
    touch "$LOG"
fi

# pironman5.sh 스크립트를 실행하고 모든 출력을 로그 파일에 기록합니다.
bash "$HOME/apps/booted/pironman5.sh" > "$LOG" 2>&1

# 로그 파일 경로를 출력하고, 파일 내용을 화면에 표시합니다.
echo "### $LOG"
cat "$LOG"
