# Nextcloud Filesystem Checkup

`checkup.py`는 WebDAV로 원격 Nextcloud 디렉터리를 점검하는 스크립트입니다.

다음 정보를 조회합니다.

- 파일 개수
- 전체 용량
- 가장 오래된 파일 시간과 경로
- 가장 최근 파일 시간과 경로
- 연결 확인용 `--conn_test`

## Files

- `checkup.py`: 원격 Nextcloud 디렉터리 점검 스크립트
- `checkup.sample.conf`: 설정 샘플 파일

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

## Usage

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

## Output

출력에는 다음 값이 포함됩니다.

- `file_count`
- `total_size`
- `oldest_file_time`
- `oldest_file_path`
- `newest_file_time`
- `newest_file_path`
- `undated_files`
