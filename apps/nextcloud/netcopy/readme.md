# Netcopy for webdav, nextcloud

`netcopy`는 Nextcloud WebDAV 서버 A의 파일을 서버 B로 증분 복사하는 도구입니다.  
중복 전송을 줄이기 위해 파일 크기, ETag, 수정 시간을 비교하고, 업로드가 끝난 뒤에는 대상 파일을 다시 내려받아 해시와 크기를 확인합니다.

## 파일 구성

- `txtoserver.py`
  Nextcloud 간 파일 복사를 수행하는 메인 스크립트입니다.
- `copytowebav.py`
  로컬 파일 또는 디렉토리를 Nextcloud WebDAV로 업로드하는 스크립트입니다.
- `input.sample.conf`
  설정 파일 샘플입니다. 실제 사용 시 `input.conf`로 복사해서 값을 채워 넣으면 됩니다.
- `copytowebav.sample.conf`
  로컬에서 Nextcloud로 올릴 때 사용하는 설정 샘플입니다.
- `skip.txt`
  이미 동일하다고 판단되어 전송하지 않은 파일의 소스/목적지 URL을 기록하는 로그 파일입니다.
- `copytowebav_skip.txt`
  로컬에서 Nextcloud로 업로드할 때 건너뛴 파일의 로그 파일입니다.

## 주요 기능

- WebDAV 기반 서버 간 파일 복사
- 로컬 파일/디렉토리에서 Nextcloud로 업로드
- 디렉토리 구조 자동 생성
- `copytowebav.py` 대상 Nextcloud 루트 아래에 전송 날짜 디렉토리(`YYYY-MMDD`, 예: `2026-0427`) 자동 생성
- 파일 크기, ETag, 수정 시간 비교를 통한 증분 복사
- 전송 대상 파일 개수와 총 용량 출력
- 전송 완료 파일 개수와 누적 용량 출력
- 업로드 후 SHA-256 해시 및 크기 비교로 무결성 검증
- 연결 테스트 모드 지원
- 종료 상태를 컬러 문자로 출력

## 준비 사항

Python 환경에서 아래 라이브러리가 필요합니다.

```bash
pip install webdavclient3
```

서버는 WebDAV 접근이 가능해야 하며, `webdav_hostname`, `webdav_root`, `username`, `password` 정보가 필요합니다.

## 설정 파일 만들기

샘플 파일을 복사해 실제 설정 파일을 준비합니다.

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/nextcloud/netcopy
cp input.sample.conf input.conf
```

예시:

```ini
[source]
webdav_hostname = https://nextcloud-a.example.com
webdav_root = /remote.php/dav/files/username/
port = 443
username = user_a
password = pass_a
root = Photos

[destination]
webdav_hostname = https://nextcloud-b.example.com
webdav_root = /remote.php/dav/files/username/
port = 443
username = user_b
password = pass_b
root = Photos

[settings]
verify_ssl = true
```

## 설정 항목 설명

### `[source]`

- `webdav_hostname`
  소스 Nextcloud 서버 주소입니다.
- `webdav_root`
  사용자 WebDAV 루트 경로입니다.
- `port`
  접속 포트입니다. 보통 HTTPS는 `443`입니다.
- `username`
  로그인 계정입니다.
- `password`
  로그인 비밀번호 또는 앱 비밀번호입니다.
- `root`
  복사 시작 디렉토리입니다. 예: `Photos`

### `[destination]`

- `source`와 같은 구조이며, 복사 대상 서버 정보를 입력합니다.

### `[settings]`

- `verify_ssl`
  `true`면 SSL 인증서를 검증합니다.
  자체 서명 인증서 환경이면 `false`가 필요할 수 있습니다.

## 실행 방법

### 1. Nextcloud -> Nextcloud

기본 설정 파일 사용:

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/nextcloud/netcopy
python3 txtoserver.py
```

직접 설정 파일 지정:

```bash
python3 /Users/tinyos/devel_opment/BerePi/apps/nextcloud/netcopy/txtoserver.py /path/to/input.conf
```

연결 테스트:

```bash
python3 txtoserver.py --conn_test
```

설정 파일을 지정해서 연결 테스트:

```bash
python3 txtoserver.py /path/to/input.conf --conn_test
```

### 2. Local -> Nextcloud

샘플 설정 파일을 복사합니다.

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/nextcloud/netcopy
cp copytowebav.sample.conf copytowebav.conf
```

예시:

```ini
[source]
path = /data/photos

[destination]
webdav_hostname = https://nextcloud.example.com
webdav_root = /remote.php/dav/files/username/
port = 443
username = user
password = app_password
root = Backup/Photos

[settings]
verify_ssl = true
```

기본 설정 파일 사용:

```bash
python3 copytowebav.py
```

직접 설정 파일 지정:

```bash
python3 copytowebav.py /path/to/copytowebav.conf
```

연결 테스트:

```bash
python3 copytowebav.py --conn_test
```

설정 파일을 지정해서 연결 테스트:

```bash
python3 copytowebav.py /path/to/copytowebav.conf --conn_test
```

## 실행 흐름

스크립트는 아래 순서로 동작합니다.

1. 설정 파일을 읽고 source/destination 정보를 확인합니다.
2. 소스와 대상 경로를 조합해 출력합니다.
3. 소스 서버에 `PROPFIND` 요청을 보내 기본 접근 가능 여부를 확인합니다.
4. 소스 서버 전체 파일 목록을 재귀적으로 스캔합니다.
5. 대상 서버 파일 목록을 읽어 비교용 메타데이터 맵을 만듭니다.
6. 전송이 필요한 파일 수와 총 용량을 계산합니다.
7. 파일별로 업로드를 수행합니다.
8. 업로드 직후 대상 파일을 다시 다운로드해 원본과 동일한지 검증합니다.
9. 누적 완료 수량과 용량을 출력합니다.
10. 모든 작업이 끝나면 성공, 실패, 전송 없음 상태를 컬러로 출력합니다.

`copytowebav.py`는 destination root 바로 아래가 아니라, 전송 시점 기준 날짜 디렉토리 `YYYY-MMDD`를 만든 뒤 그 아래에 파일을 복사합니다. 예를 들어 destination root가 `Backup/Photos`면 실제 업로드 위치는 `Backup/Photos/2026-0427/...` 형태가 됩니다.

`txtoserver.py`는 날짜 디렉토리를 만들지 않고 destination root 바로 아래에 원래 상대 경로대로 복사합니다.

`copytowebav.py`는 흐름이 거의 같지만, source를 WebDAV 대신 로컬 파일 시스템에서 읽습니다. 파일 하나를 지정하면 그 파일만 올리고, 디렉토리를 지정하면 하위 파일을 재귀적으로 탐색해 상대 경로를 유지한 채 업로드합니다.

## 출력 메시지 예시

```text
전송 대상: 파일 12개, 용량 1.42 GB
전송 완료: 파일 0/12개, 용량 0 B/1.42 GB
Uploading Photos/2026/a.jpg -> Backup/2026/a.jpg
전송 대상: 파일 12개, 용량 1.42 GB
전송 완료: 파일 1/12개, 용량 4.20 MB/1.42 GB
종료 상태: 성공
```

### 종료 상태 의미

- 초록색 `종료 상태: 성공`
  모든 전송 대상 파일이 정상적으로 복사되고 검증까지 완료된 상태입니다.
- 빨간색 `종료 상태: 실패`
  연결 실패, 업로드 실패, 검증 실패 등의 문제가 발생한 상태입니다.
- 노란색 `종료 상태: 전송할 파일 없음`
  대상 서버에 이미 동일한 파일이 있어 새로 전송할 항목이 없는 상태입니다.

## 소스코드 구조

### 상수 및 데이터 구조

- `SCRIPT_DIR`
  현재 스크립트가 있는 디렉토리입니다.
- `DEFAULT_CONFIG`
  기본 설정 파일 경로입니다.
- `DEFAULT_SKIP_LOG`
  건너뛴 파일 로그 경로입니다.
- `Progress`
  전체 파일 수, 전체 바이트 수, 완료 파일 수, 완료 바이트 수를 저장하는 데이터 클래스입니다.

### 유틸리티 함수

- `color_text()`
  ANSI 컬러 코드를 붙여 종료 상태 메시지를 보기 쉽게 만듭니다.
- `format_bytes()`
  바이트 값을 `KB`, `MB`, `GB` 단위 문자열로 변환합니다.
- `sha256_file()`
  파일의 SHA-256 해시를 계산합니다.
- `get_entry_size()`
  Nextcloud 엔트리 정보에서 파일 크기를 정수로 꺼냅니다.

### 설정 및 클라이언트 함수

- `print_usage()`
  실행 방법과 기본 설정 파일 위치를 출력합니다.
- `load_config()`
  INI 형식 설정 파일을 읽습니다.
- `build_client()`
  설정 정보를 바탕으로 `webdav3.client.Client` 객체를 생성합니다.

### 경로 처리 함수

- `normalize_root()`
  루트 경로 앞뒤 슬래시를 정리합니다.
- `normalize_remote_path()`
  원격 파일 경로를 비교하기 쉬운 형태로 정리합니다.
- `relative_from_root()`
  소스 루트를 기준으로 상대 경로를 계산합니다.
- `compose_remote_url()`
  로그 출력용 전체 WebDAV URL을 만듭니다.

### 서버 스캔 및 비교 함수

- `is_directory()`
  응답 값이 디렉토리인지 판별합니다.
- `parse_time()`
  문자열 수정 시간을 `datetime`으로 변환합니다.
- `list_tree()`
  WebDAV 디렉토리를 재귀적으로 탐색하여 파일 목록을 수집합니다.
- `build_info_map()`
  파일 경로별로 크기, ETag, 수정 시간 정보를 정리합니다.
- `should_upload()`
  소스와 대상 파일을 비교해 업로드가 필요한지 결정합니다.

### 업로드 및 검증 함수

- `ensure_dirs()`
  대상 서버에 필요한 디렉토리가 없으면 순서대로 생성합니다.
- `upload_and_verify_file()`
  소스 파일을 임시 파일로 다운로드하고 대상 서버로 업로드한 뒤,
  다시 대상 파일을 다운로드해서 해시와 크기를 비교합니다.

### 점검 및 출력 함수

- `run_source_propfind()`
  `curl PROPFIND`로 소스 서버 응답을 확인합니다.
- `run_connection_test()`
  `--conn_test` 모드에서 source/destination 연결을 확인합니다.
- `validate_paths()`
  실제 조합된 경로를 출력해 설정 실수를 줄입니다.
- `append_skip_log()`
  건너뛴 파일 정보를 `skip.txt`에 기록합니다.
- `print_transfer_summary()`
  전송 대상과 전송 완료 상태를 요약 출력합니다.

### 메인 함수

- `main()`
  설정 로드, 경로 확인, 서버 스캔, 비교, 업로드, 검증, 최종 종료 상태 출력까지 전체 흐름을 담당합니다.

### `copytowebav.py`의 로컬 전송 관련 함수

- `normalize_local_path()`
  로컬 경로를 절대 경로로 정리합니다.
- `get_local_files()`
  지정한 파일 또는 디렉토리에서 업로드 대상 파일 목록을 수집합니다.
- `validate_source_path()`
  로컬 source 경로의 존재 여부와 타입을 확인합니다.
- `validate_destination_path()`
  대상 Nextcloud WebDAV 경로를 출력해 확인합니다.
- `upload_and_verify_file()`
  로컬 파일을 업로드한 뒤 대상 파일을 다시 내려받아 동일성을 검증합니다.

## 주의 사항

- 파일마다 업로드 후 재다운로드 검증을 수행하므로, 파일 수가 많거나 큰 파일이 많으면 시간이 더 걸릴 수 있습니다.
- `skip.txt`는 실행할수록 누적 기록됩니다.
- 자체 서명 인증서를 쓰는 서버에서는 `verify_ssl = false`가 필요할 수 있습니다.
- 비밀번호 대신 Nextcloud 앱 비밀번호 사용을 권장합니다.

## 웹 버전: web_txtoserver.py

기존 `txtoserver.py`의 WebDAV 연결, 파일 비교, 디렉토리 생성, 다운로드/업로드 및 SHA-256 검증 함수를 재사용합니다. Source는 기존 CLI와 동일하게 **Nextcloud WebDAV 디렉토리**입니다.

```bash
pip install webdavclient3
python3 web_txtoserver.py --port 8080
# 선택: 초기 설정 및 체크포인트 위치 지정
python3 web_txtoserver.py --port 8090 --config input.conf --state-file /path/to/checkpoint.json
```

브라우저에서 `http://127.0.0.1:8080`을 열고 Source/Destination의 서버 URL, WebDAV 경로, 서버 포트, 사용자 이름, 앱 비밀번호, 디렉토리를 입력합니다. `input.conf`가 있으면 비밀번호를 제외한 초기 설정을 불러옵니다. 비밀번호는 웹페이지에서 입력하며 체크포인트에는 저장되지 않습니다. 웹 서버 포트는 `--port`, Nextcloud 서버 포트는 각 설정의 포트 입력칸으로 지정합니다.

1. **실행 전 확인**: 양쪽 연결과 전체 목록을 조회하여 전송 대상 파일 수 및 용량을 계산합니다. 대상 디렉토리 생성/업로드는 실행 후 진행합니다. 기존 파일 건너뛰기 정보는 CLI와 동일하게 `skip.txt`에 기록됩니다.
2. **실행 / 이어서 시작**: 검증이 끝나지 않은 파일을 전송합니다. 화면에 최근 150개 로그, 현재 파일, 완료 파일/전체 파일, 완료 용량/전체 용량, 파일 수 기준 진행률 및 실패 수가 표시됩니다. 진행률은 파일 검증이 끝날 때 갱신됩니다.
3. **일시 중단**: 현재 파일의 다운로드·업로드·재다운로드·검증을 마친 뒤 중단합니다. 대용량 파일이나 느린 서버에서는 중단까지 시간이 걸릴 수 있습니다.
4. **재개**: 같은 페이지에서는 이어서 시작을 누릅니다. 서버를 재시작한 경우 같은 설정과 비밀번호를 입력하고 실행 전 확인 후 이어서 시작합니다. 완료 기록은 기본적으로 `web_txtoserver.state.json`에 원자적으로 저장됩니다. 원본 메타데이터가 변경되거나 대상 파일이 없거나 크기가 바뀌면 완료 기록을 무효화합니다. 실패 파일은 재개 시 재시도합니다.

체크포인트는 가장 최근 작업 하나를 보관합니다. 다른 전송 작업은 별도 `--state-file`을 사용하세요. 서버 강제 종료 시 처리 중인 파일은 파일 처음부터 재전송하며, 파일 내부 바이트 위치 재개는 지원하지 않습니다. 완료 기록은 source 경로·크기·ETag·수정 시각을 기준으로 하며 대상 파일의 동일 크기 외부 수정까지 감지하지는 않습니다. 브라우저를 닫아도 서버 프로세스가 살아 있으면 작업은 계속됩니다. Ctrl+C는 현재 파일 완료 및 체크포인트 저장을 기다립니다.

기본 바인딩은 `127.0.0.1`이며 로컬 사용을 기준으로 합니다. 외부 접속이 필요하면 인증/TLS 리버스 프록시를 사용하세요. `--host 0.0.0.0 --allow-host example.com:8080`처럼 접근 주소의 Host 헤더를 허용할 수 있습니다. 이 프로그램 자체에는 사용자 로그인 기능이 없습니다. 같은 체크포인트 경로로 여러 프로세스를 동시에 실행하지 마세요.

오프라인 검증:

```bash
python3 -m unittest discover -s apps/nextcloud/netcopy -p 'test_web*.py'
```

### 웹 설정 히스토리

`실행 전 확인`을 누르면 입력 형식 검증을 통과한 설정을 `web_txtoserver.history.json`에 저장합니다. 연결 확인에 실패한 설정도 기록하며, 최근 항목부터 최대 100개를 보관하고 초과 시 가장 오래된 항목을 제거합니다. 같은 설정을 여러 번 확인한 경우도 각각 기록합니다. 페이지를 열면 최근 설정을 자동으로 불러오고, `설정 히스토리` 선택란에서 이전 설정을 선택할 수 있습니다.

비밀번호는 길이와 무관한 고정 마스크 `********`로 기록합니다. 원문이나 복원 가능한 암호문, 비밀번호 해시는 저장하지 않습니다. 불러올 때 비밀번호 입력칸은 비워지므로 양쪽 비밀번호를 다시 입력한 뒤 실행 전 확인을 진행하세요. 히스토리 파일은 소유자 읽기/쓰기 권한(0600)으로 원자적으로 저장합니다. 저장 위치는 다음과 같이 지정할 수 있습니다.

```bash
python3 web_txtoserver.py --port 8080 --history-file /path/to/history.json
```

### 서버 포트 및 전송 속도

웹에서는 **서버 URL과 서버 포트를 별도로 입력**합니다. 예: URL `http://keties.iptime.org`, Source 포트 `22080`, Destination 포트 `4001`. 내부에서 URL에 포트를 결합하여 실제 연결에 적용합니다. 빈 포트는 URL의 포트 또는 HTTP 80 / HTTPS 443을 사용합니다. 기존 URL에 포트가 포함되어 있더라도 별도 포트 입력값이 있으면 그 값이 우선합니다. 이 수정은 CLI의 `input.conf` 포트에도 적용됩니다.

`전송 속도 제한`은 MiB/s (1 MiB = 1,048,576 바이트) 단위이며 소수 입력이 가능합니다. `0`은 무제한입니다. 파일 데이터의 평균 처리 속도를 제한하며, Source 다운로드 / Destination 업로드 / 검증 다운로드에 각각 적용됩니다. 목록 조회 및 HTTP 헤더는 제한하지 않으며 네트워크 버퍼로 인해 순간 속도는 다를 수 있습니다. 속도 설정도 최근 100개 설정 히스토리에 저장되고 복원됩니다. 변경하려면 일시 중단 후 값을 입력하고 실행 전 확인을 다시 진행하세요.
