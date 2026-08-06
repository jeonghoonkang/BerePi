# txtoserver.py 동작 메모

대상 파일: `apps/nextcloud/txtoserver.py`

## 기능 요약

- Nextcloud 서버 **A(source)** 의 파일(주로 Photos)을 WebDAV로 스캔한 뒤, Nextcloud 서버 **B(destination)** 로 **중복 없이 증분 복사**합니다.
- 목적지에 동일 파일이 이미 있을 때는 업로드를 생략하고, 생략 내역을 `skip.txt`에 기록합니다.
- 비교 기준(업로드 필요 여부):
  - **파일 크기(size)** 가 다르면 업로드
  - **ETag** 가 다르면 업로드
  - **수정 시각(modified)** 이 소스가 더 최신이면 업로드
- 디렉토리 구조가 없으면 목적지에 자동 생성합니다.
- `--conn_test` 옵션으로 양쪽 서버 연결/권한을 빠르게 점검할 수 있습니다.

## 실행 방법

### 1) 준비물

- Python 3
- 의존 패키지: `webdavclient3` (모듈 경로는 `webdav3`)
- 외부 명령: `curl` (소스 서버에 대해 PROPFIND 테스트 수행)

예시 설치:

```bash
pip install webdavclient3
```

### 2) 설정 파일 준비 (`input.conf`)

기본은 현재 디렉토리의 `input.conf`를 읽습니다. (INI 형식)

구성 섹션:
- `[source]`: 소스 Nextcloud(WebDAV) 접속 정보 + `root`
- `[destination]`: 목적지 Nextcloud(WebDAV) 접속 정보 + `root`
- `[settings]`: `verify_ssl` (기본 true)

`root`는 Nextcloud 사용자 파일 영역 기준의 루트 폴더(예: `Photos`)입니다.

### 3) 실행

```bash
python apps/nextcloud/txtoserver.py
```

설정 파일 경로를 직접 지정:

```bash
python apps/nextcloud/txtoserver.py E:\path\to\input.conf
```

연결 테스트만:

```bash
python apps/nextcloud/txtoserver.py --conn_test
python apps/nextcloud/txtoserver.py E:\path\to\input.conf --conn_test
```

## 실행 과정(전체 흐름)

진입점은 `main()`이며, 마지막에 `SystemExit(main())`로 종료 코드를 반환합니다.

### 1) 인자 파싱/설정 로딩

- `print_usage()`
  - 사용법 문자열을 출력합니다. (항상 출력)
- `main()`
  - `--conn_test` 유무를 분리해서 처리합니다.
  - 설정 파일 경로가 없으면 `input.conf`를 사용합니다.
- `load_config(config_path)`
  - 설정 파일 존재 여부 확인 후 `configparser.ConfigParser()`로 로딩합니다.
- `verify_ssl = config.getboolean("settings", "verify_ssl", fallback=True)`
  - WebDAV 클라이언트의 TLS 검증 여부를 설정합니다.
- `normalize_root()`
  - `root` 값의 앞뒤 `/`를 제거해 일관된 비교/조합이 가능하게 합니다.

### 2) 경로/접속 사전 점검

- `validate_paths(section, root, label)`
  - `webdav_hostname`, `webdav_root`, `root`를 출력하고,
  - 최종 URL 조합 결과(`composed`)를 보여줍니다.
- `run_source_propfind(src_section, src_root)`
  - `curl -X PROPFIND -H "Depth: 1"`로 소스 서버에 직접 요청합니다.
  - 실패(리턴코드!=0) 시 즉시 종료합니다.
  - 목적: “서버/인증/루트 경로”가 맞는지 빠르게 확인.

### 3) WebDAV 클라이언트 구성

- `build_client(section, verify_ssl)`
  - `webdav3.client.Client`를 생성합니다.
  - `port`가 설정되어 있으면 `webdav_port`로 지정합니다.
  - `client.verify = verify_ssl`로 SSL 검증 설정을 반영합니다.

### 4) 연결 테스트 모드(`--conn_test`) 분기

- `run_connection_test(client, root, label)`
  - `client.list(root, get_info=True)` 호출이 성공하면 OK로 판단합니다.
  - 실패하면 예외를 잡아 `RuntimeError`로 감싸고, `main()`에서 종료 코드 1로 종료합니다.

### 5) 파일 트리 스캔(소스/목적지)

- `list_tree(client, root)`
  - BFS(큐) 방식으로 디렉토리를 재귀 순회합니다.
  - `client.list(current, get_info=True)` 결과의 `isdir`, `path`를 이용해
    - 폴더면 큐에 넣고
    - 파일이면 `items`에 누적합니다.
  - 내부적으로 경로 정규화를 위해 다음 함수들을 사용합니다:
    - `normalize_remote_path()`: 앞뒤 `/` 제거
    - `relative_from_root()`: 스캔 루트 기준 상대경로 계산
    - `is_directory()`: `isdir` 값이 bool/str일 수 있어 안전하게 판정

- `build_info_map(entries)`
  - 엔트리 리스트를 `{path -> (size, etag, modified_datetime)}` 맵으로 변환합니다.
  - `modified`는 `parse_time()`로 datetime으로 변환합니다.

### 6) 업로드/스킵 결정 및 전송

- `should_upload(src_info, dest_info)`
  - 목적지 정보가 없으면 업로드
  - size / etag / mtime 기준으로 업로드 필요 여부 판정

- 업로드 수행:
  - `upload_file(src_client, dest_client, src_path, dest_path)`
    - `ensure_dirs(dest_client, dest_dir)`로 목적지 폴더를 단계적으로 생성
    - 임시파일(`tempfile.NamedTemporaryFile`)에 소스를 다운로드 후 목적지에 업로드
    - 사용 WebDAV API:
      - `src_client.download_sync(remote_path=..., local_path=...)`
      - `dest_client.upload_sync(remote_path=..., local_path=...)`

- 스킵(이미 존재/동일로 판단):
  - `compose_remote_url(section, remote_path)`로 사람이 읽기 좋은 URL을 구성
  - `append_skip_log("skip.txt", src_url, dst_url)`로 기록

### 7) 결과 요약

- 업로드 수(`uploaded`)와 스킵 수(`skipped`)를 출력하고 종료 코드 0으로 종료합니다.

## 실행 중 생성/사용되는 파일

- `skip.txt`
  - 업로드 생략된 항목을 `src=... | dst=...` 형식으로 누적 기록합니다.

