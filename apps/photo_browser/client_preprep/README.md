# 업로드 전 클라이언트 사진 검사

원격 PC의 여러 사진 폴더를 읽어 가벼운 SQLite 목록을 만들고 서버의 현재 DB와 비교합니다.
사진 원본, EXIF, 로컬 파일 경로는 서버에 보내지 않습니다. SHA-256과 바이트 크기만
최대 500개씩 전송합니다. 사진을 업로드·삭제·이동하거나 서버 DB를 수정하지 않습니다.

## 준비

- 클라이언트: Python 3.10 이상. `preprep.py` 하나만 복사해도 실행 가능하며 pip 설치 불필요.
- 서버: 이 변경이 반영된 photo_browser를 재시작하고 평소처럼 소스 스캔을 완료합니다.
- 서버에서 설정한 로그인 암호 사용. HTTPS 인증서를 정상 검증합니다.

## 실행 (클라이언트 PC)

```sh
python3 preprep.py scan "/path/to/photos" "/path/to/other-photos" --db inventory.sqlite3
python3 preprep.py check --db inventory.sqlite3 --server https://photos.example.com > report.json
python3 preprep.py report --db inventory.sqlite3
```

Windows에서는 `python` 명령과 `"D:\Photos"` 같은 경로를 사용할 수 있습니다.
암호는 터미널에서 입력하며 자동화 시 `PHOTO_BROWSER_PASSWORD` 환경변수를 사용할 수 있습니다.
암호를 URL이나 명령행 인자로 넣지 않습니다. 신뢰하는 내부망에서 HTTP만 제공하는 서버는
`--allow-http`를 명시해야 합니다(이 경우 인증 정보가 암호화되지 않습니다).
서버 URL에는 필요하면 reverse proxy의 경로 접두어를 포함할 수 있습니다.

## 결과

| status | 의미 |
|---|---|
| unchecked | 스캔했지만 서버 비교를 완료하지 않음 |
| exists | SHA-256 및 크기가 같은 active 서버 DB 레코드 존재 |
| not_in_server_db | 비교 시점 active 서버 DB에 일치 기록 없음 |
| stale | 스캔 후 파일의 크기/수정 시간이 바뀌었거나 접근 불가; 재스캔 필요 |
| error | 로컬 해시 계산 실패; error 필드 확인 |

`match_count`는 서버 DB의 일치 레코드 수입니다. `local_copy_count`는 로컬의 동일 바이트
파일 수입니다. `upload_candidate=true`는 서버 DB에 없고 로컬 중복 중 대표로 선택된 파일입니다.
실제 업로드는 수행하지 않습니다. 파일명이 같아도 내용이 다르면 다르게 판별하고, 이름이
달라도 바이트가 같으면 일치합니다. 리사이즈/재인코딩한 유사 사진 판별은 지원하지 않습니다.

서버의 미스캔 파일은 비교 대상이 아닙니다. `exists`도 DB 기록 기준이며 서버 디스크의
현재 파일 존재 여부나 무결성을 재검증한 결과가 아닙니다. 휴지통/비활성 기록은 제외합니다.
각 배치는 조회 시점 DB를 사용하므로 비교 중 서버 스캔/삭제가 있으면 결과 시점이 다를 수 있습니다.

`scan`은 전체 파일을 스트리밍 해시하고 성공 시 이전 DB를 교체하여 삭제된 파일을 제거합니다.
중첩 소스 경로는 중복 등록하지 않고 심볼릭 링크 및 `._` 파일은 건너뜁니다.
지원 형식은 서버와 동일한 jpg/jpeg/png/gif/webp/mp4/mov/avi입니다.
파일별 읽기 오류는 DB에 기록하며 종료 코드 1을 반환합니다. 디렉토리 탐색 실패 시 기존 DB를 보존합니다.
스캔/비교를 같은 DB에서 동시에 실행하지 마세요. 로컬 DB와 보고서에는 로컬 경로가 들어 있습니다.

매 비교 시작 시 이전 비교 결과를 무효화합니다. 네트워크/인증/응답 오류 시 미완료 비교를
업로드 후보로 처리하지 않고 종료 코드 1을 반환합니다. 수정 시간과 크기를 유지한 내용 변경은
`check`만으로 탐지할 수 없으므로 업로드 직전에 `scan`과 `check`를 다시 실행하세요.

## 서버 API

`POST /api/client-preprep/check` — 기존 Basic/세션 인증과 `X-Photo-Browser: 1` 보호 적용.
요청: `{"files":[{"sha256":"64자리 소문자 hex", "size_bytes":123}]}`.
응답은 `schema_version: 1`, `basis: "active_database_records"`, 입력 순서의 `results`입니다.
서버 경로나 전체 DB는 반환하지 않습니다. 서버는 배치마다 DB를 한 번 읽으므로 대규모
라이브러리는 서버 DB 읽기 비용을 고려하세요.
