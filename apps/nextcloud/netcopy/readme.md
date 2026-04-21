# Netcopy

`netcopy`는 Nextcloud WebDAV 서버 A의 파일을 서버 B로 증분 복사하는 도구입니다.  
중복 전송을 줄이기 위해 파일 크기, ETag, 수정 시간을 비교하고, 업로드가 끝난 뒤에는 대상 파일을 다시 내려받아 해시와 크기를 확인합니다.

## 파일 구성

- `txtoserver.py`
  Nextcloud 간 파일 복사를 수행하는 메인 스크립트입니다.
- `input.sample.conf`
  설정 파일 샘플입니다. 실제 사용 시 `input.conf`로 복사해서 값을 채워 넣으면 됩니다.
- `skip.txt`
  이미 동일하다고 판단되어 전송하지 않은 파일의 소스/목적지 URL을 기록하는 로그 파일입니다.

## 주요 기능

- WebDAV 기반 서버 간 파일 복사
- 디렉토리 구조 자동 생성
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

## 주의 사항

- 파일마다 업로드 후 재다운로드 검증을 수행하므로, 파일 수가 많거나 큰 파일이 많으면 시간이 더 걸릴 수 있습니다.
- `skip.txt`는 실행할수록 누적 기록됩니다.
- 자체 서명 인증서를 쓰는 서버에서는 `verify_ssl = false`가 필요할 수 있습니다.
- 비밀번호 대신 Nextcloud 앱 비밀번호 사용을 권장합니다.
