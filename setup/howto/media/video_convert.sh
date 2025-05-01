!/bin/bash

# 설정 부분
SEARCH_DIR="/path/to/your/videos"  # 검색할 최상위 디렉토리
LOG_DIR="/var/log/video_converter"  # 로그 저장 디렉토리
LOCK_FILE="/tmp/video_converter.lock"  # 중복 실행 방지용 락 파일
MAIN_LOG="$LOG_DIR/conversion.log"  # 전체 작업 로그
FILE_LIST_LOG="$LOG_DIR/file_list.log"  # 변환 대상 파일 목록
CONVERTED_LOG="$LOG_DIR/converted.log"  # 성공한 변환 기록 (파일 크기 포함)

# 디렉토리 생성
mkdir -p "$LOG_DIR"

# 중복 실행 방지
if [ -f "$LOCK_FILE" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 다른 작업이 실행 중입니다. 종료합니다." >> "$MAIN_LOG"
    exit 1
fi
touch "$LOCK_FILE"

# 함수: 파일 크기 포맷팅 (KB, MB, GB)
format_size() {
    local size=$1
    if [ $size -ge 1073741824 ]; then
        echo "$(echo "scale=2; $size/1073741824" | bc) GB"
    elif [ $size -ge 1048576 ]; then
        echo "$(echo "scale=2; $size/1048576" | bc) MB"
    elif [ $size -ge 1024 ]; then
        echo "$(echo "scale=2; $size/1024" | bc) KB"
    else
        echo "$size bytes"
    fi
}

# 함수: 로그 기록
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$MAIN_LOG"
}

# 시작 로그
log "=== 변환 작업 시작 ==="

# 1. 변환 대상 파일 목록 생성 (MKV, AVI, FLV)
find "$SEARCH_DIR" -type f \( -name "*.mkv" -o -name "*.avi" -o -name "*.flv" \) > "$FILE_LIST_LOG"

# 2. 파일별 변환 실행
while IFS= read -r file; do
    dir=$(dirname "$file")
    filename=$(basename "$file")
    output="$dir/${filename%.*}.mp4"

    # MP4가 이미 있으면 건너뜀
    if [ -f "$output" ]; then
        log "건너뜀: $file (MP4가 이미 존재)"
        continue
    fi

    # 원본 파일 크기 확인
    original_size=$(stat -c %s "$file" 2>/dev/null)
    original_size_human=$(format_size "$original_size")

    # 변환 시도
    log "변환 시작: $file (크기: $original_size_human) → $output"
    if ffmpeg -i "$file" -c:v libx264 -crf 23 -preset fast -c:a aac -b:a 192k "$output" >/dev/null 2>&1; then
        # 변환된 파일 크기 확인
        converted_size=$(stat -c %s "$output" 2>/dev/null)
        converted_size_human=$(format_size "$converted_size")

        # 로그에 기록 (파일 경로 + 원본/변환 크기)
        echo "$file | 원본: $original_size_human | 변환: $converted_size_human" >> "$CONVERTED_LOG"
        log "성공: $output (크기: $converted_size_human, 압축률: $(echo "scale=2; $converted_size*100/$original_size" | bc)%)"
    else
        log "실패: $file (ffmpeg 오류)"
    fi
done < "$FILE_LIST_LOG"

# 종료 로그
log "=== 변환 작업 완료 ==="

# 락 파일 제거
rm -f "$LOCK_FILE"
