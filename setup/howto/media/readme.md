# Video converter

`video_convert.sh`는 FFmpeg를 이용해 단일 영상 파일 또는 설정 디렉터리 아래의 영상 파일을 MP4로 변환합니다. 스크립트와 설정 파일은 이 디렉터리에 함께 있으며, 어느 위치에서 실행해도 `setup/howto/media/video_convert.conf`를 사용합니다.

## 필요 프로그램

Ubuntu/WSL에서 다음 프로그램을 설치합니다.

```bash
sudo apt update
sudo apt install ffmpeg bc util-linux
```

## 설정

실행 전에 `video_convert.conf`를 환경에 맞게 수정합니다.

```bash
SEARCH_DIR="/home/tinyos/media"
LOG_DIR=/tmp/log/video_converter
OUTPUT_SUBDIR=mp4

THREADS=2
PRESET=fast
CRF=18
AUDIO_BITRATE=192k
```

- `SEARCH_DIR`: 일괄 변환할 영상 파일의 최상위 디렉터리
- `LOG_DIR`: 변환 로그 및 파일 목록을 저장할 디렉터리
- `OUTPUT_SUBDIR`: 각 원본 디렉터리 아래에 만들 출력 폴더명. 슬래시 없는 이름만 허용
- `THREADS`, `PRESET`, `CRF`, `AUDIO_BITRATE`: FFmpeg 인코딩 옵션

스크립트 실행 시 실제 사용하는 설정 파일의 절대 경로가 다음과 같이 출력됩니다.

```text
사용 설정 파일: /path/to/BerePi/setup/howto/media/video_convert.conf
이 스크립트는 위 경로의 conf 파일 설정을 기준으로 동작합니다.
```

## 실행

저장소 루트에서 실행 권한을 설정합니다.

```bash
chmod +x setup/howto/media/video_convert.sh
```

설정된 `SEARCH_DIR`의 지원 영상 파일을 재귀적으로 일괄 변환합니다.

```bash
./setup/howto/media/video_convert.sh
```

현재 위치와 관계없이 절대 경로로 실행할 수도 있습니다.

```bash
/path/to/BerePi/setup/howto/media/video_convert.sh
```

단일 파일만 변환하려면 입력 파일을 인자로 전달합니다.

```bash
./setup/howto/media/video_convert.sh "/path/to/source/sample.mov"
```

## 출력 구조

결과 MP4는 원본 옆이 아니라 원본이 있는 디렉터리 아래의 `OUTPUT_SUBDIR`에 생성됩니다.

```text
/media/project/source.mov
→ /media/project/mp4/source.mp4
```

하위 디렉터리의 파일도 각 파일이 위치한 디렉터리를 기준으로 출력 폴더가 생성됩니다.

```text
/media/project/day1/camera.mts
→ /media/project/day1/mp4/camera.mp4
```

같은 출력 MP4가 이미 존재하면 해당 파일은 건너뜁니다. 실행 중복은 `LOCK_FILE`과 `flock`으로 방지합니다.

## 지원 입력 확장자

`mkv`, `avi`, `flv`, `wmv`, `mov`, `MTS`, `m2ts`, `rvmb`, `skm`, `AVI`, `MOV`

## 오디오 추출 참고

```bash
mplayer -dumpaudio "$INPUT" -dumpfile "$OUTPUT"
ffmpeg -i video.avi -acodec copy audio.mp3
```
