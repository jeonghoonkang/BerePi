# Authoer: BerePi
!/bin/bash

# 기본 설정으로 실행
# ./video_converter.sh
# 다른 설정 파일 지정 (옵션)
# CONFIG_FILE="/path/to/custom.conf" ./video_converter.sh

# 설정 파일 로드
CONFIG_FILE="${BASH_SOURCE%.*}.conf"  # 스크립트와 동일한 이름의 .conf 파일 사용
if [ ! -f "$CONFIG_FILE" ]; then
    echo "설정 파일을 찾을 수 없습니다: $CONFIG_FILE" >&2
    exit 1
fi

# INI 파서 함수
parse_ini() {
    while IFS='= ' read -r key value; do
        if [[ $key == \[*] ]]; then
            section=${key#\[}; section=${section%\]}
        elif [[ $value ]] && [[ $section ]]; then
            eval "${section}_${key}=\${value}"
        fi
    done < "$1"
}

parse_ini "$CONFIG_FILE"

# 변수 할당
SEARCH_DIR="$directories_SEARCH_DIR"
LOG_DIR="$directories_LOG_DIR"
FFMPEG_THREADS="$ffmpeg_THREADS"
FFMPEG_PRESET="$ffmpeg_PRESET"
FFMPEG_CRF="$ffmpeg_CRF"
FFMPEG_AUDIO_BITRATE="$ffmpeg_AUDIO_BITRATE"
MAIN_LOG="$LOG_DIR/$logging_MAIN_LOG"
FILE_LIST_LOG="$LOG_DIR/$logging_FILE_LIST_LOG"
CONVERTED_LOG="$LOG_DIR/$logging_CONVERTED_LOG"
LOCK_FILE="$options_LOCK_FILE"
SKIP_EXISTING="$options_SKIP_EXISTING"


# 디렉토리 생성
mkdir -p "$LOG_DIR" || exit 1

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
    if ffmpeg -i "$file" \
        -threads "$FFMPEG_THREADS" \
        -c:v libx264 \
        -crf "$FFMPEG_CRF" \
        -preset "$FFMPEG_PRESET" \
        -c:a aac \
        -b:a "$FFMPEG_AUDIO_BITRATE" \
        "$output" >/dev/null 2>&1; then
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

