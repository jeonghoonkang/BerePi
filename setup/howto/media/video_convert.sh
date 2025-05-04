# Authoer: BerePi
#!/bin/bash

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

#parse_ini "$CONFIG_FILE"

source $CONFIG_FILE

# 변수 할당
#SEARCH_DIR="$directories_SEARCH_DIR"
#LOG_DIR="$directories_LOG_DIR"
#FFMPEG_THREADS="$ffmpeg_THREADS"
#FFMPEG_PRESET="$ffmpeg_PRESET"
#FFMPEG_CRF="$ffmpeg_CRF"
#FFMPEG_AUDIO_BITRATE="$ffmpeg_AUDIO_BITRATE"
MAIN_LOG=$LOG_DIR/$M_LOG
#FILE_LIST_LOG="$LOG_DIR/$logging_FILE_LIST_LOG"
#CONVERTED_LOG="$LOG_DIR/$logging_CONVERTED_LOG"
#LOCK_FILE="$options_LOCK_FILE"
#SKIP_EXISTING="$options_SKIP_EXISTING"

echo "Current USER: $USER"
echo "Current SHELL: $SHELL"
echo "Current PWD: $(pwd)"

# 디렉토리 생성
mkdir -p "$LOG_DIR" || exit 1

# 중복 실행 방지
if [ -f "$LOCK_FILE" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 다른 작업이 실행 중입니다." >> "$MAIN_LOG"
    read -p "LOCK 파일이 존재합니다. 강제로 삭제하고 계속하시겠습니까? yes/no: " answer
    if [ "$answer" = "yes" ]; then
        rm -f "$LOCK_FILE"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] LOCK 파일을 강제 삭제 후 작업을 시작합니다." >> "$MAIN_LOG"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 다른 작업이 실행 중입니다. 종료합니다." >> "$MAIN_LOG"
        exit 1
    fi
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Lock File을 만듭니다. " >> "$MAIN_LOG"
echo "$LOCK_FILE"

#touch "$LOCK_FILE"
#LOCK_FILE="/tmp/lock.lock"

LOCK_F=$LOCK_FILE

touch "$LOCK_F" 

touch $MAIN_LOG

fail() { 
    echo " FAIL script" >> "$MAIN_LOG"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >> "$MAIN_LOG"
    exit 1 
}

# flock을 이용한 락 획득 시도
exec 9>"$LOCK_FILE" || fail "Cannot open lock file"
flock -n 9 || fail "Another instance is running"

# 정상 동작 시작
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting process..." >> "$MAIN_LOG"

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
        log "건너뜀: $file MP4가 이미 존재"
        continue
    fi

    # 원본 파일 크기 확인
    original_size=$(stat -c %s "$file" 2>/dev/null)
    original_size_human=$(format_size "$original_size")

    # 변환 시도
    log "변환 시작: $file 크기: $original_size_human → $output"

    if ffmpeg -i "$file" \
        -threads "$THREADS" \
        -c:v libx264 \
        -crf "$CRF" \
        -preset "$PRESET" \
        -c:a aac \
        -b:a "$AUDIO_BITRATE" \
        -strict -2 \
        "$output" >/dev/null 2>&1; then
        # 변환된 파일 크기 확인
        converted_size=$(stat -c %s "$output" 2>/dev/null)
        converted_size_human=$(format_size "$converted_size")

        # 로그에 기록 (파일 경로 + 원본/변환 크기)
        echo "$file | 원본: $original_size_human | 변환: $converted_size_human" >> "$CONVERTED_LOG"
        log "성공: $output 크기: $converted_size_human, 압축률: $(echo "scale=2; $converted_size*100/$original_size" | bc)%"
    else
        log "실패: $file ffmpeg 오류"
    fi
done < "$FILE_LIST_LOG"

# 종료 로그
#log "=== 변환 작업 완료 ==="

# 락 파일 제거
rm -f $LOCK_FILE
flock -u 9
