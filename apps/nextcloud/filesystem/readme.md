# Nextcloud File system Tools

`checkup.py`와 `cleanup.py`는 WebDAV로 원격 Nextcloud `target` 디렉터리를 점검하고 정리하는 스크립트입니다.

## Files

- `common.py`: 공통 설정 로딩, WebDAV 연결, 경로/시간 처리, 재귀 listing 유틸
- `checkup.py`: 원격 Nextcloud 디렉터리 점검 스크립트
- `cleanup.py`: 오래된 원격 파일 정리 스크립트
- `cron_command_builder.html`: 점검/삭제/이동/분할 작업용 실행 명령과 `crontab` 라인을 생성하는 정적 HTML
- `checkup.sample.conf`: 설정 샘플 파일

## Checkup

`checkup.py`는 다음 정보를 조회합니다.

- 파일 개수
- 전체 용량
- 가장 오래된 파일 시간과 경로
- 가장 최근 파일 시간과 경로
- 연결 확인용 `--conn_test`

## Config

설정 파일은 INI 형식이며 `target`, `settings` 섹션을 사용합니다.

주요 항목은 다음과 같습니다.

- `webdav_hostname`: Nextcloud 서버 주소
- `webdav_root`: WebDAV root 경로
- `port`: 접속 포트
- `username`: 계정명
- `password`: 비밀번호
- `root`: 점검할 원격 디렉터리
- `verify_ssl`: SSL 검증 여부

`checkup.sample.conf` 파일은 샘플이므로, 파일 이름을 변경해서 사용해야 합니다. 예를 들어 `my_checkup.conf` 또는 `input.conf`로 복사하거나 이름을 바꾼 뒤 실제 서버 정보로 수정해서 사용하세요.

## Checkup Usage

기본 실행:

```bash
python3 apps/nextcloud/filesystem/checkup.py /path/to/your.conf
```

샘플 설정을 복사해 사용하는 예:

```bash
cp apps/nextcloud/filesystem/checkup.sample.conf apps/nextcloud/filesystem/my_checkup.conf
python3 apps/nextcloud/filesystem/checkup.py apps/nextcloud/filesystem/my_checkup.conf
```

점검 실행:

```bash
python3 apps/nextcloud/filesystem/checkup.py /path/to/your.conf
```

연결 테스트만 수행:

```bash
python3 apps/nextcloud/filesystem/checkup.py /path/to/your.conf --conn_test
```

## Cleanup

`cleanup.py`는 지정한 날짜 기준보다 오래된 파일을 찾아 삭제 후보를 먼저 보여줍니다.

- 기본 동작은 `--dry-run`
- 실제 삭제는 `--execute`일 때만 진행
- `--execute`여도 사용자가 `confirm`을 입력해야 삭제 수행
- 미리보기 로그와 실행 로그를 `apps/nextcloud/filesystem/logs/` 아래에 저장

## Cleanup Usage

기본 dry-run:

```bash
python3 apps/nextcloud/filesystem/cleanup.py /path/to/your.conf --days 10
```

명시적 dry-run:

```bash
python3 apps/nextcloud/filesystem/cleanup.py /path/to/your.conf --days 30 --dry-run
```

실제 삭제:

```bash
python3 apps/nextcloud/filesystem/cleanup.py /path/to/your.conf --days 30 --execute
```

연결 테스트:

```bash
python3 apps/nextcloud/filesystem/cleanup.py /path/to/your.conf --conn_test
```

## HTML Builder

`cron_command_builder.html`은 브라우저에서 다음 작업의 명령 생성을 돕습니다.

- `checkup.py` 점검 명령 생성
- `cleanup.py --dry-run` / `--execute` 삭제 명령 생성
- 오래된 파일 이동용 셸 명령 생성
- 대용량 파일 분할용 셸 명령 생성
- 위 명령을 감싼 `crontab` 라인 생성

## Output

출력에는 다음 값이 포함됩니다.

- `file_count`
- `total_size`
- `oldest_file_time`
- `oldest_file_path`
- `newest_file_time`
- `newest_file_path`
- `undated_files`

`cleanup.py`는 추가로 다음 정보를 출력합니다.

- 삭제 기준 날짜
- 삭제 후보 개수
- 삭제 후보 전체 용량
- 파일별 수정 시간, 경과 일수, 경로
- dry-run / execute 모드
- 로그 저장 경로
