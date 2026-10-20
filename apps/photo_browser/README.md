# BerePi Photo Browser

사진·동영상을 스캔하여 JSON으로 등록하고, 월별 병합 복사·이벤트/태그 편집·검색·휴지통 복원을 제공하는 앱입니다. 기존 폴더 탐색 화면도 유지합니다.

지원 형식은 사진 **JPG/JPEG, PNG, GIF, WebP**, 동영상 **MP4, MOV, AVI**입니다. 기존 폴더 탐색과 라이브러리 소스 스캔·DB 등록·병합 복사에 동일하게 적용되며 확장자 대소문자는 구분하지 않습니다. 동영상 메타데이터 추출에는 `ffprobe`가 필요합니다. 웹 화면의 동영상 재생 가능 여부는 브라우저와 파일의 코덱에 따라 달라지며, 앱은 재생용 형식 변환을 수행하지 않습니다.

## 구성과 처리 흐름

```text
로컬 / WebDAV / HTTP 목록
  → 파일 목록 집계 → 메타데이터·SHA-256 분석 → 월별 JSON 발행
  → 월별 병합 미리보기 → 검증 후 복사
  → 이벤트·태그·사람 지정 → 검색·브라우징
  → 휴지통 이동 → 복원 또는 확인 후 영구 삭제
```

중지·이어하기는 **스캔 및 JSON 생성**에 적용됩니다. 스캔만 실행하면 사진을 복사하지 않으며, 관리 디렉토리에 모으려면 별도로 병합 복사를 실행해야 합니다.

| 파일 | 역할 |
| --- | --- |
| `app.py` | 서버 실행, 기존 폴더 탐색 및 미디어 제공 |
| `library.py` | JSON 저장, 메타데이터, 원격 접근, 병합, 휴지통·복원 |
| `scan_engine.py` | 전체 목록 집계, 진행률, 체크포인트, 중지·이어하기, 용량 검사 |
| `library_api.py` | 라이브러리 API, 백그라운드 작업, 인증·변경 요청 검사 |
| `templates/index.html` | 화면 구성 |
| `static/library.js` | 라이브러리·설정·진행률·휴지통 화면 동작 |
| `static/app.js` | 기존 폴더 탐색 화면 동작 |
| `config.example.json` | 로컬·WebDAV 설정 예시 |

## 목차

- [설치 및 실행](#설치-및-실행)
- [라이브러리 사용 순서](#라이브러리-사용-순서)
- [설정 항목](#설정-항목)
- [진행률·중지·이어하기](#오래-걸리는-스캔-진행률중지이어하기)
- [API 사용 예시](#api-사용-예시)
- [기존 Apache 서버 활용](#기존-apache-7080-서버-활용)
- [문제 해결과 백업](#문제-해결과-백업)
- [검증](#검증)

## 설치 및 실행

저장소 루트에서 실행합니다. Python 3.10 이상이 필요합니다.

```bash
python3 -m venv apps/photo_browser/.venv
apps/photo_browser/.venv/bin/pip install -r apps/photo_browser/requirements.txt
apps/photo_browser/.venv/bin/python apps/photo_browser/app.py --directory "$HOME/Pictures"
```

브라우저: <http://127.0.0.1:7081/>

### Raspberry Pi / Linux에서 경로를 분리하는 예

다음 디렉토리는 미리 준비하고 서버 실행 계정에 원본 읽기, DB·관리 디렉토리 쓰기 권한을 부여합니다.

```text
/data/incoming/       원본 사진·동영상
/data/photo_library/  관리 복사본
/data/photo_db/       JSON DB와 체크포인트
```

```bash
apps/photo_browser/.venv/bin/python apps/photo_browser/app.py \
  --root /data --directory /data/incoming --db /data/photo_db
```

접속 후 관리 디렉토리를 `/data/photo_library`로 저장하고, 소스에는 `/data/incoming`을 등록합니다. 동영상 촬영 정보도 읽으려면 `ffprobe -version`으로 도구가 실행되는지 확인하세요.

### Windows PowerShell

저장소 루트에서 실행합니다. 아래 `E:/photos`와 하위 경로는 실제 사용할 경로로 바꾸세요. 소스 디렉토리는 미리 만들어 두어야 합니다.

```powershell
py -3 -m venv apps/photo_browser/.venv
.\apps\photo_browser\.venv\Scripts\python.exe -m pip install -r apps/photo_browser/requirements.txt
.\apps\photo_browser\.venv\Scripts\python.exe apps/photo_browser/app.py `
  --root E:/photos --directory E:/photos/incoming --db E:/photos/photo_db
```

관리 디렉토리는 `E:/photos/photo_library`, 소스는 `E:/photos/incoming`처럼 따로 지정합니다. 가상환경 활성화 없이 위 실행 파일을 직접 호출할 수 있습니다. Windows에서도 동영상 메타데이터를 읽으려면 `ffprobe.exe`가 PATH에 있어야 합니다.

### 비밀번호와 원격 인증 환경변수

다음 값은 예시이므로 실제 운영 값으로 바꿉니다. 설정 후 같은 셸에서 서버를 실행하세요.

```bash
export PHOTO_BROWSER_PASSWORD='change-this-password'
export NAS_PHOTOS_USER='photo-user'
export NAS_PHOTOS_PASSWORD='change-this-remote-password'
```

```powershell
$env:PHOTO_BROWSER_PASSWORD = 'change-this-password'
$env:NAS_PHOTOS_USER = 'photo-user'
$env:NAS_PHOTOS_PASSWORD = 'change-this-remote-password'
```

브라우저 인증 창에는 임의 사용자 이름과 `PHOTO_BROWSER_PASSWORD` 값을 입력합니다. `NAS_PHOTOS_*`는 소스의 `credential_ref`가 `NAS_PHOTOS`일 때 사용합니다. 이 인증 값은 서버 프로세스가 시작할 때 전달되는 환경에 있어야 하며, 서비스나 Gunicorn으로 실행한다면 해당 서비스 환경에도 설정합니다.

다른 기기에서도 연결하려면 `--host 0.0.0.0`을 추가합니다. 포트는 `--port 7081`로 변경할 수 있습니다. `--directory` 폴더는 실제 존재하는 경로를 지정하세요. 미지정 시 사용자 홈에서 시작합니다.

```bash
apps/photo_browser/.venv/bin/python apps/photo_browser/app.py \
  --host 0.0.0.0 --port 7081 --root /data --directory /data/photos
```

`--root`는 앱이 접근할 수 있는 **최상위 폴더**입니다. 사진이 있는 폴더 자체 또는 그 상위 폴더를 지정할 수 있습니다. `--directory`는 앱을 열었을 때 **처음 표시할 사진 폴더**이며, 작업 파일이나 관리 복사본을 저장하는 디렉토리가 아닙니다. 위 예시에서는 `/data/photos`에서 탐색을 시작하고 `/data` 내부의 다른 폴더로 이동할 수 있습니다.

사진의 관리 복사본을 저장할 **관리 디렉토리**(`managed_root`)는 앱의 `소스·스캔·병합` 설정에서 별도로 지정합니다. `--directory`를 지정해도 스캔 소스로 자동 등록되지 않습니다.

`--root` 기본값은 `/`이므로 앱 실행 계정이 읽을 수 있는 경로를 탐색할 수 있습니다. 공유 서버에서는 공개할 폴더를 `--root`로 제한하세요. 기존 폴더 탐색은 파일을 변경하지 않으며, 라이브러리의 삭제는 관리 복사본만 대상으로 합니다.

## 라이브러리 사용 순서

### CLI에서 설정·스캔 상태 확인 및 병합

웹에서 저장한 DB를 서버 없이도 조회하고 병합할 수 있습니다. 저장소 루트에서 서버와 동일한 `--db`, `--root`를 지정하세요. Python 3.10 이상과 위 설치 환경을 사용합니다.

```bash
# 저장된 설정과 실제 DB·허용 루트 확인
python3 apps/photo_browser/cli.py --db /data/photo_db --root /data config

# 등록된 모든 소스의 최신 스캔 상태·처리 수·오류·JSON 발행 여부 확인
python3 apps/photo_browser/cli.py --db /data/photo_db --root /data status
python3 apps/photo_browser/cli.py --db /data/photo_db --root /data status --source-id local_photos

# 대상 경로 미리보기 후 전체 병합 복사 실행
python3 apps/photo_browser/cli.py --db /data/photo_db --root /data merge --preview
python3 apps/photo_browser/cli.py --db /data/photo_db --root /data merge

# 일부 항목만 병합하거나 중지한 병합 이어하기
python3 apps/photo_browser/cli.py --db /data/photo_db --root /data merge --media-id MEDIA_ID
python3 apps/photo_browser/cli.py --db /data/photo_db --root /data merge --resume MERGE_ID

# 원본과 관리 복사본의 파일 수·용량·SHA-256 비교
python3 apps/photo_browser/cli.py --db /data/photo_db --root /data compare
python3 apps/photo_browser/cli.py --db /data/photo_db --root /data compare --source-id local_photos

# 빠른 크기 비교 (동일 크기의 내용 손상은 검출하지 못함)
python3 apps/photo_browser/cli.py --db /data/photo_db --root /data compare --quick
```

출력은 JSON입니다. `status`의 `scan_complete`는 스캔 완료와 월별 JSON 발행을 모두 확인하며, 개별 파일 실패는 `error_count`와 `scan.errors`에서 확인합니다. 아직 스캔하지 않은 소스는 `not_scanned`입니다. `running`은 마지막 저장 상태이므로 강제 종료 후에도 남을 수 있습니다. 실시간 서버 작업 상태는 웹 화면에서 확인하세요.

`--db`를 생략하면 `PHOTO_BROWSER_DB`, 환경변수도 없으면 `apps/photo_browser/db`를 사용합니다. 기존 설정이 없는 DB는 오류로 처리합니다. 원격 병합에는 서버와 같은 인증 환경변수를 설정해야 합니다. 병합은 동기 실행되며 종료할 때 결과와 `merge_id`를 출력합니다. `Ctrl+C`는 현재 파일 처리 후 중지 상태를 저장합니다. 중지·복사 오류는 종료 코드 1, 정상 완료와 조회는 0을 반환합니다. 원본은 유지하며 기존 대상 파일의 내용이 다르면 덮어쓰지 않습니다. 서버가 실행 중이어도 사용할 수 있지만 다른 쓰기 작업과 겹치면 기존 DB 잠금에 의해 거부됩니다.

`compare`는 원본 디렉토리를 다시 탐색하고 DB에 등록된 활성 원본·관리 복사본과 비교합니다. `sources`에는 소스별 실제 미디어 파일 수·총 바이트와 DB의 활성 항목 수·바이트를, `managed`에는 관리 디렉토리 전체 미디어 파일 수·총 바이트와 비교한 고유 복사본 수·바이트를 출력합니다. `--source-id`로 제한해도 `managed.file_count`와 `managed.total_bytes`는 전체 관리 디렉토리 집계입니다. 스캔과 같은 확장자만 대상으로 하며 AppleDouble(`._*`), 심볼릭 링크, DB·관리 디렉토리 및 `.trash`는 원본 탐색에서 제외합니다. 텍스트 파일 등은 집계하지 않습니다.

기본 검증은 현재 원본과 관리 복사본의 크기·SHA-256이 스캔 당시 값과 같은지 확인합니다. 파일 수가 같더라도 내용이 다르면 실패합니다. 중복 원본이 하나의 관리 복사본을 공유하거나 휴지통 처리한 항목이 있으면 단순 합계가 달라질 수 있으므로, 합계의 일치만으로 성공을 판정하지 않습니다. 비활성 원본은 복사 검증에서 제외하고 `excluded_inactive_count`로 표시합니다. 추가로 남아 있는 관리 파일은 전체 집계에 포함하되 복사 실패로 판정하지 않습니다.

`ok: true` 및 종료 코드 0은 선택한 소스에서 문제를 발견하지 않았다는 뜻입니다. 문제는 `issues`에 원본 누락·변경, 미스캔 파일(`not_scanned`), 미등록 복사본(`copy_not_registered`), 복사본 누락·접근 실패, 내용 불일치(`copy_mismatch`) 등으로 표시하며 종료 코드 1을 반환합니다. `verified_item_count`는 원본과 하나 이상의 등록된 복사본이 검증을 통과한 항목 수입니다. 파일과 메타데이터를 수정하지 않으며, 서버 작업과 겹치지 않도록 DB 작업 잠금을 획득합니다. 외부 프로그램의 파일 변경까지 막지는 않으므로 원본 파일 변경이 없는 동안 실행하세요. 원격 소스는 목록을 다시 읽고 파일을 내려받아 비교하므로 인증 환경변수·네트워크와 임시 공간이 필요하고 시간이 걸릴 수 있습니다.

1. `소스·스캔·병합`에서 **관리 디렉토리**를 먼저 저장합니다. `--root` 안에 있으며 DB와 분리된 경로를 지정하세요.
2. 소스 ID, 프로토콜, 경로, 카테고리, 소유자 ID를 등록합니다. 추가 디렉토리도 별도 소스로 등록할 수 있습니다.
3. `스캔 / JSON 생성`으로 등록합니다. 로컬 증분 스캔은 용량·수정 시각이 같은 항목의 재분석을 생략합니다. `처음부터 전체 재스캔`은 목록·해시·메타데이터를 처음부터 다시 읽습니다. 중지한 스캔은 `중단 지점부터 이어하기`로 재개합니다.
4. `전체 병합 미리보기`의 대상 경로를 확인하고 `전체 병합 실행`을 누릅니다. 소스 원본은 유지합니다.
5. 라이브러리에서 사진을 선택해 이벤트 이름, 태그, 사람 ID, 카테고리, 소유자를 지정합니다. 체크한 필드만 **교체**하며 쉼표로 여러 값을 입력합니다. 재스캔해도 입력값을 보존합니다.
6. 이벤트·태그·사람·카테고리·소유자·날짜 범위 필터를 조합합니다. 하루만 검색하려면 시작일과 종료일을 같게 설정합니다. 사진을 누르면 파일 경로, 촬영 위치, 날짜 근거, 검증 결과 등 상세 JSON을 확인할 수 있습니다.
7. `정밀 파일 확인`은 선택 파일의 존재·용량·SHA-256을 확인합니다. 원격 파일은 내려받아 검사하므로 시간이 걸릴 수 있습니다.

기본 DB는 `apps/photo_browser/db`입니다. `--db` 또는 `PHOTO_BROWSER_DB`로 바꿀 수 있습니다. 서버를 중지한 상태에서 `config.example.json`을 DB의 `config.json`으로 복사해 경로를 수정해도 됩니다. Windows에서는 `E:/photos`처럼 경로를 지정할 수 있습니다. 프론트엔드에 입력하는 경로는 서버의 경로입니다.

### 저장 경로의 구분

| 경로 | 용도 | 예시 |
| --- | --- | --- |
| 허용 루트 `--root` | 로컬 파일 접근을 허용할 경계 | `/data` |
| 시작 폴더 `--directory` | 앱을 열었을 때 처음 표시할 폴더 | `/data/photos` |
| 소스 `sources[].root` | 원본을 읽을 디렉토리 또는 원격 URL | `/data/incoming` |
| 관리 경로 `managed_root` | 병합 복사본과 `.trash` 보관 | `/data/photo_library` |
| DB `--db` | 설정, 인덱스, 메타데이터, 체크포인트 보관 | `/data/photo_db` |

**입력 소스 사진 디렉토리**는 `소스·스캔·병합 → 소스 등록`에서 경로(`sources[].root`)로 지정합니다. `/data/photos1`, `/data/photos2`처럼 여러 원본 폴더를 별도 소스로 등록한 뒤 각각 스캔할 수 있습니다. `--directory`는 화면의 탐색 시작 위치만 지정하며 병합 입력 소스를 등록하지 않습니다.

**출력 디렉토리와 병합 파일이 생성되는 디렉토리는 관리 디렉토리(`managed_root`)를 뜻합니다.** `소스·스캔·병합 → 관리 디렉토리`에서 `/data/photo_library` 같은 경로를 입력하고 저장하세요. 별도의 `--output` 실행 옵션은 없습니다. 실제 사진·동영상 복사본은 다음 구조로 생성됩니다.

```text
/data/photo_library/카테고리/소유자/연도/월/원본파일명
# 예: /data/photo_library/family/default/2026/10/IMG_0001.jpg
```

촬영 날짜가 없는 파일은 연도와 월에 `unknown/unknown`을 사용합니다. 병합은 여러 사진을 한 파일로 합치는 작업이 아니라, 원본 파일을 유지하면서 위 폴더 구조에 복사하는 작업입니다. 같은 DB와 관리 디렉토리를 유지하면 첫 번째 소스 병합 후 두 번째 소스를 병합해도 결과가 같은 라이브러리에 누적됩니다. 대상 경로에 같은 내용의 파일이 있으면 재사용하며, 내용이 다르면 덮어쓰지 않고 오류로 기록합니다.

`--db`는 설정·인덱스·메타데이터·체크포인트 등 JSON 파일의 저장 위치입니다. 사진 복사본은 DB가 아니라 관리 디렉토리에 저장됩니다. 프론트엔드의 **현재 경로 설정**에서 입력 소스, 출력 관리 디렉토리, DB 경로와 각 역할을 확인할 수 있습니다.

관리 경로는 허용 루트 내부의 별도 하위 디렉토리여야 하며 DB와 서로 포함 관계가 될 수 없습니다. 관리 경로 자체나 DB를 스캔 소스로 지정하지 마세요. 상위 디렉토리를 스캔할 때는 관리 경로·DB·디렉토리 심볼릭 링크를 순회 대상에서 제외합니다. DB는 별도 디스크에 지정할 수도 있지만, 관리 복사본과 로컬 소스는 허용 루트 안에 있어야 합니다.

최초 자동 생성되는 관리 경로는 기본적으로 `DB 상위 디렉토리/library`입니다. 제한된 `--root`를 사용했다면 이 기본 경로가 허용 루트 밖일 수 있으므로, 첫 스캔 전에 설정 화면에서 실제 경로를 저장하세요.

### 권장 폴더 배치

원본 사진, 병합 복사본, JSON DB를 같은 상위 폴더 아래의 서로 분리된 폴더에 두면 역할을 구분하기 쉽습니다.

```text
/data/photo_system/
├── originals/                 # 입력 원본
│   ├── phone/
│   ├── camera/
│   └── old_backup/
├── photo_library/             # 병합 복사본 출력
│   └── family/default/2026/10/IMG_0001.jpg
└── db/                        # JSON 설정·메타데이터·작업 기록
```

저장소 루트에서 다음과 같이 실행합니다.

```bash
apps/photo_browser/.venv/bin/python apps/photo_browser/app.py \
  --root /data/photo_system \
  --directory /data/photo_system/originals \
  --db /data/photo_system/db
```

`소스·스캔·병합`에서 관리 디렉토리를 `/data/photo_system/photo_library`로 저장하고, 아래 원본 폴더들을 별도 소스로 등록한 다음 각각 스캔하고 병합합니다.

| 소스 ID | 원본 경로 |
| --- | --- |
| `phone` | `/data/photo_system/originals/phone` |
| `camera` | `/data/photo_system/originals/camera` |
| `old_backup` | `/data/photo_system/originals/old_backup` |

`originals` 전체를 소스로 등록했다면 그 하위의 `phone` 등을 다시 별도 소스로 등록하는 중첩은 피하세요. DB와 관리 디렉토리는 서로 포함되지 않게 유지합니다. 백업할 때는 관리 복사본과 DB를 함께 보관해야 앱에서 추가한 태그와 원본·복사본 위치 관계도 복원할 수 있습니다. 앱에서 입력한 태그는 JSON DB에 저장되며 사진 파일 내부에 새로 기록되지 않습니다.

### JSON 경로 설계 권장안 (향후 개선)

**현재 구현은 사진 항목의 `locations`에 절대 경로와 URI를 저장합니다.** 병합 복사가 성공하면 같은 사진 항목에 `role: managed` 위치가 추가되며 원본 위치와 공통 태그·촬영 정보는 유지됩니다. 아래 상대 경로 구조는 아직 구현되지 않은 개선 제안입니다. 적용하려면 경로를 읽고 쓰는 코드와 기존 DB를 함께 변환해야 하므로 기존 JSON만 직접 수정하지 마세요.

장기적으로는 설정에 실제 저장 위치인 절대 경로를 모으고, 개별 사진에는 기준점과 상대 경로를 저장하는 구성을 권장합니다. 다음은 필요한 필드만 발췌한 설정 예시입니다.

```json
{
  "managed_root": "/data/photo_system/photo_library",
  "sources": [
    {
      "source_id": "phone",
      "protocol": "file",
      "root": "/data/photo_system/originals/phone"
    }
  ]
}
```

개별 사진 항목의 제안 구조는 다음과 같습니다.

```json
{
  "media_id": "고유ID",
  "sha256": "파일내용해시",
  "classification": {
    "tags": ["가족", "여행"]
  },
  "locations": [
    {
      "role": "source",
      "source_id": "phone",
      "relative_path": "DCIM/IMG_0001.jpg"
    },
    {
      "role": "managed",
      "relative_path": "family/default/2026/10/IMG_0001.jpg"
    }
  ]
}
```

원본은 `source_id`에 해당하는 소스의 `root`와 상대 경로를 합쳐 찾고, 관리 복사본은 `managed_root`와 상대 경로를 합쳐 찾도록 합니다. 태그 등 공통 메타데이터는 사진 항목 한 곳에서 관리합니다. 이 구조에서는 저장 장치나 상위 폴더가 바뀌어도 설정의 기준 경로만 변경할 수 있습니다. 구현 시 상대 경로가 기준 폴더 밖으로 벗어나지 않도록 검증하고, 원격 소스 URL 처리와 기존 절대 경로 DB의 변환도 함께 지원해야 합니다.

### JSON 구조 예시 (현재 구현)

월별 청크는 `schema_version`, `item_count`, `items`를 포함합니다. 다음은 핵심 필드만 발췌한 예시이며, 실제 파일에는 수정 시각·해상도·검증 결과 등이 추가됩니다.

```json
{
  "schema_version": 1,
  "item_count": 1,
  "items": [
    {
      "media_id": "9b43f64a446b4178aa4aa18ade9f707a",
      "name": "IMG_1234.jpg",
      "media_type": "image",
      "size_bytes": 4281530,
      "sha256": "SHA-256 해시 문자열",
      "classification": {
        "category_id": "family",
        "owner_id": "person001",
        "person_ids": ["person001", "person002"],
        "events": ["제주도 가족여행"],
        "tags": ["여행", "바다"]
      },
      "capture": {
        "captured_at": "2026-10-20T15:30:00+09:00",
        "date_key": "2026-10-20",
        "date_basis": "exif.DateTimeOriginal",
        "location": null
      },
      "locations": [
        {
          "source_id": "local_photos",
          "role": "source",
          "protocol": "file",
          "location_type": "local",
          "host": "raspberrypi",
          "path": "/data/incoming/IMG_1234.jpg",
          "uri": "file:///data/incoming/IMG_1234.jpg",
          "status": "available"
        }
      ],
      "lifecycle": {"status": "active"}
    }
  ]
}
```

`owner_id`는 저장 경로를 나누는 소유자이고, `person_ids`는 사진과 관련된 사람들입니다. 이벤트는 현재 별도 이벤트 사전 ID가 아닌 **사진별 이름 배열**로 저장합니다. 이벤트 이름·태그·사람 ID는 정확히 일치하는 값으로 필터링하며, 이름 전체 변경은 해당 사진들을 선택해 일괄 편집합니다.

```text
db/
  config.json
  index.json                      # 현재 세대의 JSON 목록·날짜 범위·필터 인덱스
  media/family/person001/2026/10/
    media_<세대ID>_000001.json     # 같은 월의 미디어 최대 100개
    media_<세대ID>_000002.json
  duplicates/<세대ID>.json         # 동일 파일 및 촬영 시각·GPS 후보
  duplicates/latest.json          # 최신 중복 목록 경로
  scans/<스캔ID>.json
  scans/sessions/<소스ID>.json     # 최신 스캔 세션 참조
  scans/sessions/<스캔ID>/
    state.json                    # 진행률·중지 사유·여유 공간
    inventory.jsonl               # 발견한 파일 목록
    results.jsonl                 # 완료한 파일의 메타데이터·오류 저널
  plans/<작업ID>.json
  jobs/<작업ID>.json
  trash/<휴지통ID>.json
  cache/                          # 원격 미리보기 캐시

관리 디렉토리/
  family/person001/2026/10/<SHA-256>.jpg
  .trash/<휴지통ID>/family/person001/2026/10/<SHA-256>.jpg
```

각 미디어에는 고유 `media_id`, 이벤트 이름 목록(`classification.events`), 태그, 사람 ID, 촬영 정보, 파일 크기, SHA-256, 원본과 관리 복사본 목록(`locations`), 검증 결과, 삭제 상태를 기록합니다. 각 물리적 원본은 별도 항목으로 추적하며, 동일 내용은 중복 그룹으로 연결합니다. 같은 월·분류·소유자에서 동일 해시와 확장자를 가진 관리 복사본은 재사용합니다. 파일명은 충돌 방지를 위해 해시를 사용하며 원래 이름은 JSON과 화면에 보존합니다.

JSON은 임시 파일 작성 후 교체하고, 모든 청크가 완성된 후 `index.json`을 교체합니다. 이전 세대 JSON은 장애 복구를 위해 남습니다. 직접 `media` 아래 모든 파일을 합산하지 말고 **index.json에 기재된 청크만** 읽으세요. 현재 버전은 자동 정리 기능이 없으므로 대규모 라이브러리에서는 이전 세대와 캐시의 디스크 사용량을 관리해야 합니다. 필터 검색은 인덱스에서 청크를 좁힌 뒤 해당 JSON을 읽습니다. 전용 DB 검색 엔진은 아닙니다.

### 원격 소스

- **WebDAV**: Depth 1 PROPFIND로 하위 디렉토리를 순회하고 미디어를 GET으로 내려받아 분석합니다.
- **HTTP**: 소스 루트의 `manifest.json` 목록을 사용합니다. 일반 HTML 디렉토리 목록은 지원하지 않습니다. 아래 예시에서 실제 URL은 `<소스 루트>/camera/photo.jpg`입니다.

```json
{
  "files": [
    {"path": "camera/photo.jpg", "modified": "2026-10-20T12:00:00+09:00"},
    {"path": "camera/clip.mp4", "modified": "2026-10-20T12:01:00+09:00"}
  ]
}
```

원격 인증은 `credential_ref`에 `NAS_PHOTOS`를 지정하면 `NAS_PHOTOS_USER`, `NAS_PHOTOS_PASSWORD` 환경변수를 사용합니다. 비밀번호는 JSON에 저장하지 않습니다. 인증은 HTTP Basic이므로 원격 운영에는 HTTPS를 사용하세요. 저장소 바깥 URL과 리디렉션은 허용하지 않습니다. 원격 스캔은 현재 매번 파일을 다운로드합니다. 소스 등록을 해제하면 해당 원격 소스를 통한 재다운로드도 불가능하므로 필요한 병합을 먼저 완료하세요.

### 촬영 날짜·위치와 중복

라이브러리는 사진 EXIF `DateTimeOriginal`과 GPS, 동영상 `ffprobe` 메타데이터를 읽습니다. 동영상 분석에는 시스템의 `ffprobe`가 필요합니다(예: Raspberry Pi에서 `sudo apt install ffmpeg`). 도구가 없거나 메타데이터가 손상된 경우 오류를 기록하고 나머지 파일 정보를 저장합니다.

로컬 날짜는 촬영일 → 실제 생성일(운영체제가 제공할 때) → 수정일 순서입니다. Linux ctime은 생성일로 사용하지 않습니다. EXIF 시간대가 없으면 시각을 추정하지 않고 `timezone_status: unknown`으로 기록하며 원래 촬영일로 분류합니다. 원격 파일은 촬영일이 없으면 서버의 수정일을 사용하고, 그것도 없으면 `unknown/unknown`에 분류합니다. GPS가 없는 사진은 촬영 위치가 `null`입니다.

확정 중복은 SHA-256이 같은 항목입니다. 촬영 시각 문자열이 같고 GPS 좌표를 소수점 4자리로 반올림한 값이 같은 항목은 **후보**로 따로 저장합니다. 사이즈가 다른 사진도 후보가 될 수 있지만 연속 촬영을 동일 사진으로 확정하지 않습니다. 현재 시각적 해시 비교나 얼굴 인식은 포함하지 않습니다.

### 휴지통·복구·영구 삭제

일반 삭제는 **관리 복사본만** 관리 디렉토리의 `.trash`로 이동하고 라이브러리에서 숨깁니다. 복사 전 항목은 목록에서만 숨깁니다. 로컬·원격 소스 원본은 삭제하지 않으며, 재스캔해도 같은 소스 경로의 삭제 기록을 보존합니다. 다른 활성 항목이 공유 중인 관리 파일은 유지합니다.

삭제 직후 `실행 취소` 또는 휴지통의 `복원`을 사용할 수 있습니다. 복원 경로에 파일이 있으면 덮어쓰지 않고 충돌을 안내합니다. 영구 삭제는 **대상 확인 → 일회용 확인 문구 입력 → 최종 확인**을 거칩니다. 자동 영구 삭제는 하지 않습니다. 영구 삭제 후에도 소스 원본과 JSON 삭제 기록은 남습니다. 원격 미리보기 캐시와 이전 세대 메타데이터도 자동 삭제 대상이 아닙니다.

다른 휴지통 항목이 동일한 관리 파일을 공유하면 그 항목의 복원 가능성을 유지하기 위해 실제 바이트는 보존합니다. 마지막 참조 항목까지 영구 삭제할 때 해당 휴지통 파일을 제거합니다.

파일 이동 전 휴지통 기록을 저장합니다. 실패 또는 중단된 `moving`, `recovery_required`, `restoring` 항목은 휴지통에서 복원을 시도할 수 있습니다. `db/.write.lock`은 운영체제 파일 잠금을 사용하므로 프로세스 종료 시 잠금이 해제됩니다. 파일 자체는 남아도 정상이며 실행 중 삭제하지 마세요. 병합 중단 후 재실행하면 이미 검증된 해시 경로의 파일을 재사용합니다. 디스크 장애 중에는 DB와 관리 디렉토리를 함께 백업한 뒤 복구하세요.

이벤트·카테고리 편집은 JSON을 갱신합니다. 이미 복사한 파일의 물리적 이동은 자동 실행하지 않습니다. 필요하면 병합을 재실행하여 새 분류 경로에 복사할 수 있으며 이전 위치도 추적합니다. 관리 복사본이 등록된 뒤 관리 루트를 바꾸는 기능은 제공하지 않습니다.

### 접근 및 실행 방식

기본 서버는 localhost에 바인딩됩니다. `PHOTO_BROWSER_PASSWORD`를 설정하면 모든 페이지·API에 HTTP Basic 인증을 적용합니다(사용자 이름은 임의 입력). 외부 연결에는 HTTPS 또는 Apache 인증을 사용하고 접근 가능한 경로를 `--root`로 제한하세요. 변경 API는 `X-Photo-Browser: 1` 헤더와 동일 Origin 검사를 요구합니다.

작업은 단일 백그라운드 워커에서 순서대로 실행되며 상태를 폴링합니다. **서버 프로세스는 1개**로 운영하세요. 작업 상태는 `db/jobs`에 저장하며 페이지를 새로고침해도 실행 중인 작업의 상태 표시와 중지 버튼을 복원합니다. 서버 재시작 시 실행 중이던 작업은 `interrupted`로 표시하고 사용자가 이어하기를 선택하도록 합니다. 영구 삭제 확인 토큰은 메모리에만 있으므로 재시작하면 다시 확인해야 합니다.

### 오래 걸리는 스캔: 진행률·중지·이어하기

- **목록 집계**: 이미지·동영상 경로만 먼저 탐색합니다. 집계 중에는 발견한 파일 수를 표시하며, 집계가 끝난 뒤 정확한 전체 개수와 처리 진행률(처리/전체, %)을 표시합니다. 처음 연결한 디렉토리의 정확한 전체 개수를 탐색 없이 즉시 알 수는 없습니다.
- **파일 분석**: 현재 경로, 신규·갱신·변경 없음·제외·오류 개수를 표시합니다. 해시 계산은 블록 단위로 중지 요청을 확인하며, 원격 다운로드도 블록 단위로 확인합니다.
- **중지하고 저장**: 진행 카드의 버튼을 누르면 완료한 파일의 저널과 진행 상태를 저장하고 워커를 종료합니다. 충분한 공간이 있으면 완료 부분의 월별 JSON도 발행합니다. 원본과 이벤트·태그는 지우지 않습니다.
- **중단 지점부터 이어하기**: 같은 소스의 저장된 목록과 결과를 읽어 다음 미처리 파일부터 시작합니다. 중단 당시 처리 중이던 파일은 다시 처리합니다. 목록 집계 중 멈췄다면 목록 탐색을 다시 하되 이미 기록한 경로는 중복 추가하지 않습니다. 원격 다운로드의 바이트 위치까지 재개하는 기능은 아닙니다.
- **처음부터 전체 재스캔**: 새 세션에서 목록과 메타데이터·해시를 전부 다시 조사합니다. 기존 이벤트·태그·삭제 기록은 유지합니다. 이전 중간 세션 대신 새 세션이 최신 이어하기 대상이 됩니다.
- **디스크 용량 감시**: 스캔 시작 전·각 파일 처리 전·해시/원격 다운로드 중·JSON 발행 중에 DB 디스크 여유 공간을 확인합니다. 원격 다운로드는 임시 디스크도 따로 확인합니다. 기본 안전 여유 공간은 **512 MiB**이며 설정 화면 또는 `config.json`의 `scan_min_free_mb`로 변경할 수 있습니다(최소 32 MiB). 안전 여유 공간 외에 남은 파일의 JSON 예상 용량과 결과 발행 예상 용량도 고려합니다.
- **공간 부족 일시 정지**: `paused_low_space`로 작업을 종료하고 여유/예상 필요 용량을 경고합니다. 자동으로 재개하지 않으며, 공간을 확보한 다음 이어하기를 누르세요. 월별 JSON을 발행할 공간이 부족해도 결과 저널을 남기므로 재분석 없이 발행부터 이어할 수 있습니다. 단, 디스크가 실제로 완전히 찼거나 쓰기 장애가 나면 마지막으로 정상 저장한 저널까지만 복구할 수 있습니다.

목록과 처리 결과는 100개 또는 약 1초 간격으로 flush/fsync하고 중지·일시 정지 시에도 저장합니다. 비정상 종료 후에는 정상 기록된 JSONL 행까지만 재사용하고 마지막 불완전한 행은 잘라냅니다. 처리 목록은 해당 스캔의 스냅샷이므로 스캔 도중 새로 추가한 파일은 다음 신규 스캔에서 발견합니다. 중지된 동안 소스 설정을 변경했다면 처음부터 재스캔하세요. 네트워크 응답이나 `ffprobe` 호출을 기다리는 동안의 중지는 해당 호출 종료/타임아웃 이후 반영될 수 있습니다(원격 요청 타임아웃 60초, ffprobe 30초).

스캔 제어 API 예시(변경 요청에는 `X-Photo-Browser: 1` 헤더 필요):

```text
POST /api/scan                    {"source_id":"local_photos","mode":"incremental"}
POST /api/scan                    {"source_id":"local_photos","mode":"resume"}
POST /api/scan                    {"source_id":"local_photos","mode":"restart"}
GET  /api/jobs                    최근 작업 목록
GET  /api/jobs/<job_id>           진행률·현재 파일·디스크·상태
POST /api/jobs/<job_id>/stop      저장 후 중지 요청
GET  /api/scans                   소스별 최신 체크포인트
```

이 중지·이어하기·진행률·공간 감시는 스캔 및 JSON 생성 작업에 적용됩니다. 병합 복사와 정밀 검사는 기존 방식으로 실행합니다.

#### 실행 방식 선택

| 화면 버튼 / API 모드 | 동작 | 기존 정보 |
| --- | --- | --- |
| 스캔 / JSON 생성 / `incremental` | 새 목록 집계 후 로컬 용량·수정 시각이 바뀐 파일을 분석 | 이벤트·태그·삭제 상태 유지 |
| 중단 지점부터 이어하기 / `resume` | 최신 세션의 미처리 파일부터 계속 | 기존 전체 개수와 처리 결과 사용 |
| 처음부터 전체 재스캔 / `restart` | 새 세션에서 목록·메타데이터·해시를 전부 재검사 | 기존 이벤트·태그·삭제 상태 유지 |

`incremental`도 새 세션을 만듭니다. 중단한 작업을 이어가려면 반드시 `resume`을 선택하세요. `resume`은 이전 세션의 전체 검사 여부를 그대로 사용합니다. 이미 완료한 세션은 이어할 수 없으며, 새 파일을 찾으려면 신규 스캔을 실행합니다.

#### 상태와 진행률 해석

| `status` | 의미 | 다음 동작 |
| --- | --- | --- |
| `queued` | 다른 작업 종료를 기다림 | 대기 또는 중지 요청 |
| `running` | 목록 집계·분석·JSON 발행 중 | 진행 카드 확인 |
| `stopping` | 중지 요청 접수, 처리 정리·저장 중 | 저장 완료까지 대기 |
| `stopped` | 사용자 요청으로 저장 후 중지 | 이어하기 또는 처음부터 실행 |
| `paused_low_space` | 여유 공간 부족 예상 또는 쓰기 공간 부족 | 공간 확보 후 이어하기 |
| `interrupted` | 서버 재시작으로 실행 작업이 중단됨 | 이어하기 |
| `failed` | 처리 또는 저장 중 오류 | 원인 해결 후 이어하기 또는 재스캔 |
| `completed` | 작업 종료 | 오류 목록과 발행 여부 확인 |

스캔의 `phase`는 `listing`(목록 집계), `processing`(분석), `publishing`(월별 JSON 발행), `done`(완료)으로 구분합니다. 처리 비율이 100%여도 JSON 발행이 남을 수 있으므로 `completed`와 `published: true`까지 확인하세요. 개별 파일 오류가 있어도 스캔은 `completed`로 종료될 수 있으며, 오류 파일은 신규 스캔으로 다시 검사합니다. 완료 세션의 `resume`으로 오류 파일만 재시도하는 기능은 없습니다.

`processed`에는 신규·갱신·변경 없음·삭제 상태로 제외한 항목·오류 항목이 모두 포함됩니다. 스캔 중 결과는 저널에 쌓이며, 일반 라이브러리 화면에는 월별 JSON이 발행된 시점에 반영됩니다. 공간 부족으로 `published: false`라면 처리 결과가 사라진 것이 아니라 발행이 보류된 상태일 수 있습니다.

용량 예상은 남은 파일당 약 16 KiB의 JSON 여유와 최소 작업 여유를 고려합니다. 최종 발행 전에는 전체 메타데이터 직렬화 크기도 반영합니다. 이 값은 사진을 모두 병합 복사할 때 필요한 용량의 계산값이 아닙니다. 여유 공간 기준을 낮추기보다 DB·임시 디스크의 실제 사용량을 먼저 확인하세요.

## 설정 항목

`config.example.json`을 참고해 프론트엔드에서 저장하거나, 서버를 중지한 상태에서 `db/config.json`을 편집합니다. 설정 변경만으로 스캔이 자동 시작되지는 않습니다.

| 설정 | 기본값 / 규칙 |
| --- | --- |
| `schema_version` | 현재 `1` |
| `managed_root` | 로컬 관리 복사본 저장 경로 |
| `scan_min_free_mb` | 기본 `512`; `32`~`1048576` 범위의 정수, 단위 MiB |
| `sources` | 여러 저장소 설정 목록 |
| `sources[].source_id` | 중복되지 않는 소스 ID |
| `sources[].protocol` | `file`, `webdav`, `http`; 생략 시 `file` |
| `sources[].root` | 로컬 경로 또는 쿼리·인증정보 없는 HTTP(S) URL |
| `sources[].category` | 기본 `family` |
| `sources[].owner_id` | 기본 `default` |
| `sources[].recursive` | 기본 `true`; HTTP는 manifest에 나열된 미디어를 처리 |
| `sources[].credential_ref` | 원격 Basic 인증 환경변수 접두사, 선택 사항 |

소스·카테고리·소유자 ID는 문자·숫자·밑줄·하이픈으로 1~80자이며 경로 구분자는 사용할 수 없습니다. Windows 예약 장치 이름도 허용하지 않습니다. 이벤트·태그·사람 목록은 각 필드 최대 100개, 각 값 최대 200자입니다.

| 실행 인수 | 환경변수 | 기본값 |
| --- | --- | --- |
| `--root` | `PHOTO_BROWSER_ROOT` | `/` |
| `--directory` | `PHOTO_BROWSER_START` | 사용자 홈; 허용 루트 밖이면 허용 루트로 조정 |
| `--db` | `PHOTO_BROWSER_DB` | 앱 디렉토리의 `db` |
| `--host` | 없음 | `127.0.0.1` |
| `--port` | 없음 | `7081` |
| 없음 | `PHOTO_BROWSER_PASSWORD` | 미설정 시 앱 자체 인증 없음 |

명령행으로 지정한 경로가 해당 환경변수보다 우선합니다. `--directory`는 기존 폴더 탐색의 시작 경로이며 **스캔 소스 등록을 대신하지 않습니다**. Windows에서 `/` 기본 루트는 실행 드라이브의 루트로 해석되므로 운영 시 `--root`를 명시하는 편이 좋습니다.

## API 사용 예시

아래는 서버 로컬에서 실행하는 Bash 예시입니다. 비밀번호를 설정한 서버에서는 각 요청에 `--user "user:$PHOTO_BROWSER_PASSWORD"`를 추가합니다. Apache 경유 시 기본 URL에 `/photo-browser`를 포함하세요. PowerShell에서는 `curl` 별칭 대신 `curl.exe`를 사용하거나 `Invoke-RestMethod`로 JSON을 전송합니다.

```bash
# 스캔 시작: 응답의 job_id를 보관합니다.
curl --fail-with-body -X POST http://127.0.0.1:7081/api/scan \
  -H 'Content-Type: application/json' -H 'X-Photo-Browser: 1' \
  --data '{"source_id":"local_photos","mode":"incremental"}'

# JOB_ID를 위 응답의 실제 값으로 바꿉니다.
curl --fail-with-body http://127.0.0.1:7081/api/jobs/JOB_ID

# 저장 후 중지 요청. 응답 직후가 아니라 stopped 상태가 된 뒤 중지가 완료됩니다.
curl --fail-with-body -X POST http://127.0.0.1:7081/api/jobs/JOB_ID/stop \
  -H 'X-Photo-Browser: 1'

# 중단한 세션 이어하기
curl --fail-with-body -X POST http://127.0.0.1:7081/api/scan \
  -H 'Content-Type: application/json' -H 'X-Photo-Browser: 1' \
  --data '{"source_id":"local_photos","mode":"resume"}'
```

스캔·병합·검사 시작은 HTTP `202`와 `job_id`를 반환합니다. `202`는 완료가 아니라 접수를 뜻하므로 작업 상태를 확인해야 합니다. 작업 실행 중 발생한 오류는 HTTP `200`인 상태 조회 응답 안의 `status`, `error`, `result.warning`, `result.errors`에 기록될 수 있습니다.

| API | 기능 |
| --- | --- |
| `GET /api/config`, `PUT /api/config` | 전체 설정 읽기·저장 |
| `GET /api/library` | 미디어 검색 및 페이지 조회 |
| `GET /api/library/<media_id>` | 상세 정보 |
| `GET /api/library/<media_id>/file` | 이미지·동영상 제공 |
| `PATCH /api/library` | `ids`와 `changes`로 분류 일괄 교체 |
| `GET /api/facets` | 현재 이벤트·태그·사람·카테고리·소유자 목록 |
| `POST /api/merge` | `{"preview":true}` 미리보기 또는 `false` 복사 실행; 선택 `ids` 지원 |
| `POST /api/verify` | `{"ids":["미디어ID"],"full":true}` 정밀 검사 |
| `GET /api/duplicates` | 확정 중복·후보 그룹 |
| `GET /api/trash`, `POST /api/trash` | 휴지통 조회·`ids` 항목 이동 |
| `POST /api/trash/<trash_id>/restore` | 복원 |
| `POST /api/trash/<trash_id>/prepare` | 영구 삭제용 토큰·확인 문구 발급 |
| `POST /api/trash/<trash_id>/purge` | `token`, `phrase` 검증 후 영구 삭제 |

`GET /api/library`는 `event`, `tag`, `person`, `category`, `owner`, `from`, `to`, `type`, `q`, `offset`, `limit`를 지원합니다. `type`은 `image` 또는 `video`, `limit`은 최대 100입니다. 날짜 범위는 양 끝 날짜를 포함합니다. 영구 삭제 확인 토큰은 5분 동안 유효하며 한 번 사용하면 소모됩니다. 프론트엔드에서는 대상 목록 확인·문구 입력·최종 확인 절차를 추가로 제공합니다.

## 기존 폴더 탐색

- 경로 직접 입력, 상위 폴더 및 하위 폴더 이동
- 날짜별 그룹과 날짜 필터 (**서버 현지 시간의 파일 수정일 기준**, EXIF 촬영일 아님)
- 하위 폴더 포함 재귀 검색, 이미지/동영상 필터
- 이미지/GIF 원본 미리보기, MP4 재생 및 구간 요청(Range) 지원
- 클릭해서 확대, 좌우 버튼/방향키로 이동, Esc로 닫기
- 100개씩 표시, 검색 결과 최대 20,000개 (도달 시 안내)

## 기존 Apache 7080 서버 활용

Apache는 웹페이지 요청을 Python 앱으로 전달합니다. **정적 HTML 복사만으로는 시스템 폴더를 스캔할 수 없으므로 Python 서버도 함께 실행해야 합니다.** 기존 Apache의 포트나 DocumentRoot를 변경할 필요가 없습니다.

먼저 위의 독립 서버를 `127.0.0.1:7081`에서 실행합니다. 지속 운영에는 같은 가상환경에 Gunicorn을 설치해 사용할 수 있습니다 (Linux/macOS).

```bash
apps/photo_browser/.venv/bin/pip install gunicorn
cd apps/photo_browser
PHOTO_BROWSER_ROOT=/data PHOTO_BROWSER_START=/data/photos \
  .venv/bin/gunicorn --bind 127.0.0.1:7081 --workers 1 --threads 4 --timeout 120 'app:create_app()'
```

Apache의 **기존 7080 VirtualHost 블록 안에** 다음을 추가합니다. 같은 내용은 `apache/photo-browser.conf`에도 있습니다. 해당 파일을 VirtualHost 안에서 절대 경로로 `Include`해도 됩니다.

```apache
RedirectMatch 302 ^/photo-browser$ /photo-browser/
ProxyPreserveHost On
ProxyPass        /photo-browser/ http://127.0.0.1:7081/
ProxyPassReverse /photo-browser/ http://127.0.0.1:7081/
```

기존에 `ProxyPass / ...` 규칙이 있다면 위 규칙을 그보다 먼저 배치하세요. `proxy`, `proxy_http`, `alias` 모듈이 필요합니다. Debian/Ubuntu에서는:

```bash
sudo a2enmod proxy proxy_http alias
sudo apachectl configtest
sudo systemctl reload apache2
```

macOS/Homebrew 등에서는 Apache 설정의 해당 `LoadModule`을 활성화하고, 해당 설치 방식의 재시작 명령을 사용하세요. 설정 문법 검사는 `apachectl configtest`입니다.

접속: `http://서버주소:7080/photo-browser/`

페이지의 경로는 **Python 서버가 실행되는 시스템의 경로**입니다. 접속한 PC의 디렉토리는 서버에서 볼 수 없습니다. 파일 읽기 권한 역시 Python 실행 계정 기준입니다. Apache 설정 예시만 제공하며 시스템 설정을 자동 변경하지 않습니다.

## 동작 참고

GIF는 원본 애니메이션으로 표시합니다. MP4 목록은 재생 버튼으로 표시하고 클릭 시 동영상을 로드합니다. MP4 내부 코덱이 브라우저에서 지원되어야 재생됩니다. 이미지는 별도 축소 파일 없이 원본을 지연 로딩하므로 큰 이미지가 많으면 전송량이 늘어날 수 있습니다. 재귀 검색은 요청마다 다시 수행합니다.

라이브러리 스캔은 JPG/JPEG, PNG, GIF, WebP, MP4, MOV를 지원합니다. 기존 폴더 탐색은 JPG/JPEG, PNG, GIF, MP4를 지원합니다. MOV도 실제 재생 여부는 브라우저와 내부 코덱에 따라 달라집니다.

## 문제 해결과 백업

| 증상 | 확인 및 해결 |
| --- | --- |
| 집계 중에 전체 개수·백분율이 나오지 않음 | 목록 탐색 단계입니다. 발견 개수는 표시하며 집계 완료 후 전체 개수를 확정합니다. |
| 중지를 눌렀는데 바로 끝나지 않음 | `stopping` 상태인지 확인합니다. 네트워크·동영상 분석 호출이나 JSON 저장이 끝날 때까지 기다립니다. |
| 이어하기 버튼이 비활성화됨 | 아직 저장된 세션이 없거나 실행 중·완료 상태일 수 있습니다. 작업 상태 새로고침 후 확인합니다. |
| 소스 설정이 변경되었다는 오류 | 중단 당시 설정과 현재 설정이 다릅니다. 원래 소스 설정으로 되돌리거나 처음부터 재스캔합니다. |
| 100%인데 라이브러리에 보이지 않음 | `phase`, `published`, `warning`을 확인합니다. JSON 발행이 진행 중이거나 공간 부족으로 보류되었을 수 있습니다. |
| 디스크 여유가 있어도 일시 정지함 | 설정된 안전 여유 공간 외에 남은 JSON·발행 예상 용량도 필요합니다. 원격 스캔은 임시 디스크도 확인합니다. |
| 미디어가 없거나 날짜가 예상과 다름 | 지원 확장자, 서버 파일 권한, 촬영 정보 유무와 `capture.date_basis`를 확인합니다. 기존 폴더 화면은 수정일 기준입니다. |
| 원격 HTTP 스캔이 실패함 | 루트 아래 `manifest.json`, 상대 경로, 인증 환경변수와 리디렉션 여부를 확인합니다. |
| 수정 요청이 403으로 거절됨 | 변경 API 헤더와 Origin을 확인합니다. Apache 경유 시 `ProxyPreserveHost On`을 적용합니다. |
| 복원 경로 충돌 | 원래 위치에 다른 파일이 생겼는지 확인합니다. 기존 파일을 별도로 보존하고 충돌을 해소한 뒤 복원합니다. |
| 휴지통을 비워도 공간이 적게 늘어남 | 원본·다른 항목과 공유 중인 파일·이전 JSON 세대·원격 캐시는 남아 있습니다. |

백업 전에는 스캔의 `중지하고 저장`을 누르고 상태가 종료되었는지 확인한 다음 서버를 중지합니다. **DB 전체와 관리 디렉토리 전체(`.trash` 포함)**를 함께 백업하세요. DB에는 인덱스뿐 아니라 진행 저널·휴지통 복구 경로도 있으므로 `index.json`만 복사해서는 복구할 수 없습니다. 인증 환경변수와 원격 원본은 별도로 보존합니다.

복구할 때는 우선 같은 경로에 DB와 관리 디렉토리를 복원하고, 동일한 `--root`·`--db` 설정으로 서버를 시작합니다. 저장된 작업 상태를 확인한 후 이어하기 또는 휴지통 복원을 선택합니다. 원본 경로나 호스트를 바꾼 경우에는 기존 체크포인트를 그대로 재사용하기보다 소스를 다시 등록해 재스캔합니다.

자동 정리 명령은 제공하지 않습니다. 실행 중인 DB의 세대 JSON·저널·휴지통 기록을 임의로 삭제하지 마세요. 특히 `index.json`이 참조하는 청크, 이어할 세션의 `inventory.jsonl`·`results.jsonl`, 복원 전 휴지통 파일과 기록은 보존해야 합니다.

## 검증

```bash
cd apps/photo_browser
.venv/bin/python -m unittest discover -v
```

Windows에서는 저장소 루트에서 다음과 같이 실행합니다.

```powershell
.\apps\photo_browser\.venv\Scripts\python.exe -m unittest discover -s apps/photo_browser -v
```

`test_app.py`는 기존 폴더 탐색·파일 제공·경로 경계를, `test_library.py`는 월별 분할·병합 검증·모의 HTTP/WebDAV·휴지통을, `test_scan_engine.py`는 중지·이어하기·전체 재스캔·용량 부족·저널 손상·별도 프로세스 강제 종료 후 복구를 검사합니다. 테스트는 임시 디렉토리와 로컬 모의 서버를 사용하며 실제 사진 저장소나 원격 계정에 연결하지 않습니다.

### 폴더 스캔 개수 제한

`--limit 100`을 추가하면 **기존 폴더 탐색**에서 스캔 시작을 누를 때마다
지원 사진·동영상을 최대 100개까지만 수집하고 중단합니다. 하위 폴더 포함에도
같은 한도가 적용됩니다. 기본값은 20000이며 1 이상의 정수만 허용합니다.
전체를 스캔한 뒤 100개를 표시하는 방식이 아니라 탐색 중 먼저 찾은 100개를
수집한 후 수정일순으로 표시합니다. 소스·스캔·병합의 JSON 라이브러리 스캔에는
적용되지 않습니다. 실행만으로 자동 스캔을 시작하지 않습니다.

```bash
cd ~/devel_opment/BerePi/apps/photo_browser
.venv/bin/python app.py --host 0.0.0.0 \
  --root "$HOME/bk_dir/tinyosmooo_photo/BK" \
  --directory "$HOME/bk_dir/tinyosmooo_photo/BK/photo" --limit 100
```

### 병합 중지와 이어하기

전체 병합 실행 중 작업 카드의 **중지하고 저장**을 누르면 현재 파일의 복사·검증을
마친 후 진행 상태와 관리 복사본 정보를 저장합니다. 중지된 카드의 **병합 이어하기**로
남은 파일을 처리할 수 있으며 서버 재시작 후에도 사용할 수 있습니다.
진행 상태는 DB의 `merges/`에 저장됩니다. 실행 중에는 25개마다 체크포인트를 저장하며,
강제 종료 후 이어갈 때 마지막 체크포인트 이후 파일은 다시 확인하고 같은 내용이면
재사용합니다. 관리 디렉토리를 변경한 작업은 이어갈 수 없습니다.

### 기존 폴더 탐색에서 전체 개수·용량 확인과 추가 불러오기

`스캔 시작`을 누르면 선택 폴더의 지원 미디어 전체 개수와 총 파일 용량을 집계합니다. `하위 폴더 포함`을 선택하면 하위 폴더도 집계하며, 읽지 못한 항목은 합계에서 제외하고 별도로 안내합니다. 총 용량은 원본 사진·동영상의 파일 크기 합계이며 브라우저 메모리나 전송량을 뜻하지 않습니다.

파일 목록은 `--limit`(기본 20,000개) 단위로 가져옵니다. **다음 N개 불러오기**로 남은 목록을 추가 조회할 수 있고, 화면에는 전체 개수·총 용량·불러온 개수·남은 개수가 표시됩니다. 전체 개수가 불러올 수 있는 최종 개수이며, 정확히 한도만큼 있는 경우에는 추가 버튼이 표시되지 않습니다. **불러온 결과 100개 더 표시**는 이미 가져온 목록의 화면 표시만 늘립니다. 날짜·형식 필터는 현재 불러온 목록에 적용됩니다.

추가 조회마다 전체 파일 수와 용량을 다시 확인하므로 큰 폴더에서는 시간이 걸릴 수 있습니다. 조회 중 파일이 추가·삭제·이동되면 묶음 사이에 누락이나 중복이 생길 수 있으므로 `스캔 시작`으로 갱신하세요. 이 기능은 폴더 조회이며 라이브러리 스캔·JSON 등록·병합 복사를 실행하지 않습니다.

### 미디어 라이브러리의 기준 날짜 탐색

`미디어 라이브러리`의 **기준 날짜**를 선택하면 해당 날짜의 사진·동영상을 먼저 표시합니다. 선택일 당일의 파일 전체와, 선택일 이전·이후에서 시간상 가까운 파일을 각각 최대 `--limit ÷ 2`개(소수점 버림)씩 조회 범위에 포함합니다. 기본 `--limit 20000`이면 이전 최대 10,000개 + 당일 전체 + 이후 최대 10,000개입니다. 날짜를 알 수 없는 항목은 기준 날짜 탐색에서 제외합니다.

화면은 100개씩 조회하며 **이전**은 더 최근 시간으로, **다음**은 더 과거 시간으로 이동합니다. 기준 날짜의 첫 화면은 당일 파일부터 시작하고, 당일 파일이 없으면 가까운 이전 날짜부터 표시합니다. 이전 날짜 파일도 없으면 이후 날짜의 가까운 파일을 표시합니다. 개수 안내에는 당일 개수, 전후 포함 개수와 전체 후보 수, 각 방향의 최대 개수가 표시됩니다. 시작일·종료일과 태그 등 다른 검색 조건도 함께 적용되므로 범위를 좁히면 전후 파일이 제외될 수 있습니다. 기준 날짜를 비우면 일반 목록으로 돌아갑니다. 이 기능은 기존 DB를 조회하며 원본 스캔이나 병합 복사를 실행하지 않습니다.
