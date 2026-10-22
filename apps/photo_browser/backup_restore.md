# Photo Browser 백업과 복원

이 문서는 `backup.py`와 `cli.py`에 구현된 백업·검증·복원 동작을 설명합니다. 명령은 별도 안내가 없으면 BerePi 저장소 루트에서 실행하며, 예시 경로는 실제 서버 설정으로 변경해야 합니다.

## 1. 무엇을 백업하는가

현재 백업은 **병합해서 정리한 사진 라이브러리를 다른 저장소나 서버로 옮기고 복구하기 위한 기능**입니다. JSON DB 전체와 관리 디렉토리(`managed_root`) 전체를 함께 보관합니다.

| 구분 | 포함 여부와 설명 |
| --- | --- |
| JSON DB | 설정, 인덱스, 사진 정보, 이벤트·태그·사람·분류 정보 포함 |
| 작업·복구 기록 | DB 안의 스캔 체크포인트, 병합 기록, JSON·HTML 보고서 포함 |
| managed 파일 | 관리 디렉토리 안의 사진·동영상 및 일반 파일 포함 |
| 휴지통 | managed 아래 `.trash`와 DB의 휴지통 기록 포함 |
| 캐시·다운로드 | DB 안에 남아 있는 캐시와 다운로드 ZIP도 포함 |
| 이전 DB 세대 | DB 전체를 복사하므로 현재 인덱스가 참조하지 않는 이전 세대 파일도 포함 |
| 원본 소스 파일 | **포함하지 않음**. 로컬 원본·마운트 원본·WebDAV·HTTP 원본은 별도 보존 필요 |
| 앱 코드·실행 환경 | 포함하지 않음. 새 서버에 코드와 Python 의존성 설치 필요 |
| 인증 환경변수 | 포함하지 않음. 새 서버에서 별도 설정 필요 |
| `.write.lock` | 백업 파일 목록에서 제외. 복원한 앱이 필요할 때 다시 생성 |

심볼릭 링크 및 일반 파일이 아닌 항목은 백업 오류로 처리합니다. 파일을 기준으로 수집하므로 비어 있는 하위 디렉토리의 구조 자체는 보존하지 않습니다. 백업 루트의 `db/`와 `managed/`는 생성합니다.

**업로드만 하고 아직 병합하지 않은 파일도 주의해야 합니다.** 업로드 저장 위치가 managed 밖이라면 해당 파일은 이 백업에 포함되지 않습니다. 업로드 폴더를 소스로 등록하고 스캔·병합을 마치거나 원본 폴더를 별도로 백업하세요.

## 2. 원본 파일과 병합 파일의 차이

원본은 사용자가 기존에 보관하던 폴더에 있습니다. 병합은 원본을 유지하면서 managed 아래에 복사본을 만듭니다.

```text
원본 소스 — 현재 백업의 파일 수집 대상 아님
/data/originals/photo_box/여행사진/카메라/IMG_5392.JPG

병합 복사본 — 현재 백업 대상
/data/photo-library/managed/family/tinyos/2024/04/IMG_5392.JPG
```

관리 디렉토리의 기본 구조는 다음과 같습니다.

```text
managed_root/카테고리/소유자ID/연도/월/파일명
```

- **일자 디렉토리는 만들지 않습니다.** 일자는 DB의 `capture.date_key` 등으로 관리합니다.
- 촬영 날짜를 알 수 없으면 연도와 월은 `unknown/unknown`입니다.
- 파일 이름 충돌로 병합 과정에서 `_중복`, `_중복_2` 등이 붙었으면 그 이름을 그대로 백업합니다.
- 백업·복원은 파일을 다시 날짜별로 분류하지 않습니다. **백업 당시의 managed 구조를 유지**합니다.
- 사진·동영상 바이트를 재인코딩하거나 EXIF를 새로 기록하지 않습니다. 저장 경로가 바뀌어도 내용은 원본과 동일한 바이트입니다.

따라서 **현재 백업을 다른 서버에 복원하면 병합된 구조의 라이브러리가 생깁니다.** 원래의 `여행사진/카메라/` 같은 원본 폴더 구성을 재생성하는 기능은 없습니다. 원본 구조까지 보존하려면 원본 소스 디렉토리도 별도 백업해야 합니다.

## 3. 백업 형식과 자동 선택

두 가지 형식을 지원합니다.

| 형식 | 사용 방법 | 결과 |
| --- | --- | --- |
| ZIP 압축 | 대상 이름을 `.zip`으로 지정하거나 `--format zip` 사용 | 백업 파일 하나 |
| 디렉토리 | `.zip` 이외의 대상 이름 또는 `--format directory` 사용 | 압축하지 않은 백업 폴더 |

`--format`을 명시하면 확장자보다 우선합니다. 기존 폴더 백업도 계속 검증·복원할 수 있습니다.

ZIP은 ZIP64와 DEFLATE 압축을 사용합니다. 압축은 무손실이며 사진·동영상의 해상도와 화질을 바꾸지 않습니다. 이미 압축된 미디어는 용량 감소가 작거나 부가 정보 때문에 일부 증가할 수도 있습니다.

ZIP 예시:

```text
photo-library-20261022.zip
├── manifest.json
├── db/
│   ├── config.json
│   ├── index.json
│   ├── media/family/tinyos/2024/04/media_<세대ID>_000001.json
│   ├── duplicates/...
│   ├── scans/...
│   ├── merges/...
│   ├── reports/...
│   └── trash/...
└── managed/
    ├── family/tinyos/2024/04/IMG_5392.JPG
    └── .trash/...
```

폴더 백업도 같은 최상위 `manifest.json`, `db/`, `managed/` 구조를 사용합니다. 실제 하위 항목은 해당 라이브러리 상태에 따라 다릅니다.

## 4. 경로와 검증 정보를 어떻게 저장하는가

### manifest.json

ZIP 최상위의 `manifest.json`은 백업 전체의 설명서이자 파일 검증 목록입니다. 아래는 가상 경로와 값으로 작성한 **일부 필드 예제**이며 실제 파일에는 모든 대상 파일의 기록이 들어갑니다.

```json
{
  "format": "photo-browser-backup",
  "version": 1,
  "status": "complete",
  "container": "zip",
  "created_at": "2026-10-22T04:00:00+00:00",
  "original_db": "/old-server/photo-library/db",
  "original_managed_root": "/old-server/photo-library/managed",
  "original_db_uri": "file:///old-server/photo-library/db",
  "original_managed_uri": "file:///old-server/photo-library/managed",
  "original_allowed_root": "/old-server",
  "source_roots": [
    {
      "source_id": "photo_box",
      "protocol": "file",
      "root": "/old-server/originals/photo_box"
    }
  ],
  "includes_original_sources": false,
  "active_items_without_managed_copy": 0
}
```

추가로 `file_count`, `total_bytes`, `files`를 저장합니다. `files`의 각 항목에는 다음 정보가 있습니다.

| 필드 | 의미 |
| --- | --- |
| `path` | `db/...` 또는 `managed/...`로 시작하는 백업 내부 상대 경로 |
| `size_bytes` | 압축 전 파일 크기 |
| `sha256` | 파일 내용의 SHA-256 |
| `mtime_ns` | 파일 수정 시각, Unix epoch 기준 나노초 |

기존 버전에서 생성한 폴더 백업에는 `original_allowed_root`, `source_roots`, `container`가 없을 수 있습니다. 기존 DB·managed 경로와 검증 기록으로 복원할 수 있습니다.

### DB의 위치 정보

`db/config.json`의 `managed_root`는 병합 출력 위치이고 `sources[].root`는 원본 위치입니다. 사진별 JSON의 `locations`에는 원본(`role: source`)과 관리 복사본(`role: managed`) 위치가 함께 기록됩니다.

```json
{
  "locations": [
    {
      "role": "source",
      "source_id": "photo_box",
      "protocol": "file",
      "path": "/old-server/originals/photo_box/IMG_5392.JPG",
      "uri": "file:///old-server/originals/photo_box/IMG_5392.JPG",
      "status": "available"
    },
    {
      "role": "managed",
      "protocol": "file",
      "path": "/old-server/photo-library/managed/family/tinyos/2024/04/IMG_5392.JPG",
      "uri": "file:///old-server/photo-library/managed/family/tinyos/2024/04/IMG_5392.JPG",
      "status": "available"
    }
  ]
}
```

이벤트·태그·사람·분류는 사진별 JSON의 `classification`, 촬영 정보는 `capture`에 저장됩니다. 백업과 복원에서 이 정보는 유지합니다. JSON 청크는 카테고리/소유자/연도/월로 나누고 하나에 최대 100개 항목을 저장하며 `index.json`이 현재 청크 목록을 참조합니다.

## 5. 백업 전 준비

1. 필요한 사진의 스캔과 병합을 완료합니다.
2. 실행 중인 스캔·병합은 `중지하고 저장` 후 종료 상태를 확인합니다. 업로드도 완료하거나 중지합니다.
3. 일관된 결과를 위해 웹서버와 외부 파일 변경 작업을 중지합니다.
4. 웹 화면의 현재 경로 설정 또는 CLI `config`로 실제 DB·managed·허용 루트를 확인합니다.
5. 백업 대상의 쓰기 권한과 여유 공간을 확인합니다. 백업은 DB·managed와 서로 포함되지 않는 별도 경로에 둡니다. 원본 스캔 경로 아래에도 두지 않는 것이 좋습니다.
6. 기존 백업을 덮어쓰지 않도록 매번 새 이름을 지정합니다.

백업은 DB 쓰기 잠금을 획득합니다. 다른 DB 쓰기 작업과 겹치면 거부될 수 있습니다. 업로드나 외부 프로그램 등 DB 잠금으로 제어되지 않는 파일 변경도 있으므로 서버를 중지하는 절차가 가장 확실합니다. `.write.lock` 파일이 남아 있다는 이유만으로 실행 중 삭제하지 마세요. 잠금은 운영체제가 관리합니다.

## 6. Linux에서 ZIP 백업 생성

다음 예제에서는 DB가 `/data/photo-library/db`, 서버 허용 루트가 `/data`, 백업 저장소가 `/backup`이라고 가정합니다. `/backup`은 외장 디스크나 NAS 마운트 경로로 바꿀 수 있습니다.

가상환경이 없다면 먼저 준비합니다.

```bash
python3 -m venv apps/photo_browser/.venv
apps/photo_browser/.venv/bin/pip install -r apps/photo_browser/requirements.txt
```

설정 확인:

```bash
apps/photo_browser/.venv/bin/python apps/photo_browser/cli.py \
  --db /data/photo-library/db --root /data config
```

ZIP 백업 생성:

```bash
apps/photo_browser/.venv/bin/python apps/photo_browser/cli.py \
  --db /data/photo-library/db --root /data \
  backup --format zip --destination /backup/photo-library-20261022.zip
```

`--format zip`을 생략해도 대상이 `.zip`으로 끝나면 ZIP을 생성합니다. managed 경로는 지정한 DB 설정에서 읽으므로 별도 인수가 필요하지 않습니다. 대상 ZIP은 미리 만들지 않습니다.

완료 출력에서 확인할 항목:

| 항목 | 확인 사항 |
| --- | --- |
| `status` | `completed`이어야 함 |
| `backup` | 실제 저장한 ZIP 경로 |
| `file_count` | DB 파일과 관리 파일을 합친 수이며 사진 수와는 다름 |
| `total_bytes` | 압축 전 대상 파일 총 크기 |
| `archive_bytes` | 실제 ZIP 파일 크기 |
| `active_items_without_managed_copy` | 완전한 활성 사진 이전을 위해 0인지 확인 |

**`active_items_without_managed_copy`가 0보다 크면 백업 생성은 성공할 수 있지만 해당 사진의 바이트가 빠져 있습니다.** 해당 항목의 메타데이터만 DB에 포함됩니다. 필요한 병합을 먼저 완료한 뒤 새 이름으로 다시 백업하세요. 이 수치는 활성 항목 기준이며 원본 폴더 전체의 누락 파일 수를 뜻하지 않습니다.

## 7. 백업 검증과 다른 서버로 전송

백업 ZIP을 별도로 압축 해제하지 않고 검증합니다.

```bash
apps/photo_browser/.venv/bin/python apps/photo_browser/cli.py \
  backup-check --backup /backup/photo-library-20261022.zip
```

`status: verified`이면 파일 목록·크기·SHA-256 검증에 성공한 것입니다. ZIP 백업 생성 자체도 마지막에 다시 읽어 검증하지만, 전송 후에는 다시 검사해야 합니다.

SSH를 사용하는 전송 예제:

```bash
scp -p /backup/photo-library-20261022.zip user@new-host:/backup/
```

새 서버의 `/backup`은 미리 준비하고 실제 계정과 호스트를 지정합니다. 외장 디스크를 옮겨도 됩니다. **ZIP 파일은 새 서버의 읽을 수 있는 아무 위치에 둘 수 있으며 이전 서버와 같은 경로일 필요가 없습니다.**

ZIP은 파일 하나 전체를 옮깁니다. 폴더 형식이라면 `manifest.json`, `db/`, `managed/`와 `.trash` 등 숨김 항목을 포함한 폴더 전체를 옮깁니다. 새 서버에 앱 코드와 Python 의존성을 설치한 후 같은 `backup-check` 명령으로 전송 결과를 확인합니다.

## 8. 새 서버에서 복원

복원할 경로의 상위 디렉토리에 쓰기 권한과 공간이 있어야 합니다. 예제의 `/data/restored-photos`는 **아직 존재하지 않는 새 디렉토리**여야 합니다. 백업 ZIP과 복원 경로는 서로 포함되지 않아야 합니다.

```bash
apps/photo_browser/.venv/bin/python apps/photo_browser/cli.py \
  restore --backup /backup/photo-library-20261022.zip \
  --destination /data/restored-photos
```

복원 명령에는 이전 서버의 `--db`나 `--root`를 지정할 필요가 없습니다. 백업 안의 manifest와 DB를 사용합니다.

성공 결과는 `status: completed`, `db`, `managed_root`, `root` 등을 반환하며 다음 구조를 생성합니다.

```text
/data/restored-photos/
├── db/
├── managed/
└── restore.json
```

`restore.json`에는 백업 위치, 복원 실행 시각, 새 DB·관리 루트, 파일 수·바이트 수, 관리 복사본 없는 활성 항목 수를 기록합니다.

일반 압축 해제 프로그램으로 ZIP을 풀기만 하면 DB의 이전 경로가 그대로 남습니다. **앱의 `restore` 명령으로 복원해야 경로 연결까지 처리됩니다.**

## 9. 복원할 때 변경되는 경로

| 항목 | 처리 |
| --- | --- |
| `config.json`의 `managed_root` | 새 복원 경로의 `managed/`로 변경 |
| JSON에 기록된 이전 DB·managed 경로 및 URI 참조 | 새 `db/`, `managed/` 경로로 변경 |
| 관리 파일 위치·휴지통 이동 경로·구조화된 작업 기록 | 해당 DB·managed 경로 참조를 갱신 |
| 이벤트·태그·사람·분류와 촬영 정보 | 유지 |
| 별도로 보관된 원본 소스 경로·URI | 이전 값 유지. 새 서버에서 필요시 재설정 |
| 과거 HTML 보고서·일반 텍스트 경로 히스토리 | 당시 내용 유지. 이전 서버 경로가 표시될 수 있음 |
| 원래 백업 ZIP/폴더 | 변경하지 않음 |

예를 들어 관리 파일 경로는 다음처럼 변경됩니다.

```text
이전: /old-server/photo-library/managed/family/tinyos/2024/04/IMG_5392.JPG
이후: /data/restored-photos/managed/family/tinyos/2024/04/IMG_5392.JPG
```

사진 파일 수정 시각은 폴더 백업에서 `copy2`, ZIP 복원에서 manifest의 `mtime_ns`로 보존합니다. 파일시스템에 따라 시각 정밀도·권한 보존 범위는 달라질 수 있으며 생성 시각과 소유권의 완전한 보존을 보장하지 않습니다.

복원한 DB는 경로 정보를 변경했으므로 백업 당시 DB와 바이트 단위로 같을 필요는 없습니다. `backup-check`는 **원래 백업 ZIP/폴더**에 실행합니다. 복원 결과는 `restore.json`, 새 설정과 실제 사진 열기로 확인하세요.

## 10. 복원 후 서버 실행과 확인

설정 확인:

```bash
apps/photo_browser/.venv/bin/python apps/photo_browser/cli.py \
  --db /data/restored-photos/db --root /data/restored-photos config
```

서버 실행:

```bash
apps/photo_browser/.venv/bin/python apps/photo_browser/app.py \
  --root /data/restored-photos \
  --db /data/restored-photos/db \
  --directory /data/restored-photos/managed
```

| 실행 인수 | 역할 |
| --- | --- |
| `--root` | 앱이 접근할 수 있는 로컬 파일 경계 |
| `--db` | 사용할 JSON DB 위치 |
| `--directory` | 기존 폴더 탐색의 시작 위치. 원본 소스로 자동 등록되지 않음 |

라이브러리에서 사진·동영상을 열고 이벤트·태그·사람 정보와 휴지통 기록을 확인하세요. 원본이 연결되지 않아도 정상 관리 복사본이 있으면 해당 파일을 열 수 있습니다.

**복원 후 사진을 보기 위해 스캔이나 병합을 다시 실행할 필요는 없습니다.**

원본을 다시 스캔·병합하려면 실제 원본 저장소를 연결하고 소스 경로·인증 환경변수를 맞춰야 합니다. 원본이 현재 `--root` 밖에 있다면 그 원본과 복원된 DB·managed를 함께 포함하는 적절한 허용 루트로 실행하세요. 원본 위치를 변경했다면 이전 스캔을 이어하기보다 새 스캔이 필요할 수 있습니다.

`compare` 명령은 현재 연결된 원본과 비교하는 기능입니다. 원본이 없는 새 서버에서 누락을 보고한다고 해서 백업 검증이나 managed 복원이 실패한 것은 아닙니다.

## 11. 복원 후 병합하면 파일이 두 배로 생기는가

일반적으로 같은 관리 경로와 같은 내용의 파일이 있으면 병합에서 재사용합니다. `--directory`에 managed를 지정했다고 해서 managed가 새로운 원본 소스로 등록되지는 않습니다.

다음 경우는 구분해야 합니다.

| 상황 | 공간 사용 |
| --- | --- |
| ZIP을 보관한 채 복원 | ZIP 용량 + 복원한 DB·managed 용량 사용 |
| 분류·날짜와 파일 내용이 같은 상태에서 병합 재실행 | 기존 관리 파일 재사용. 작업·DB 기록 등은 증가할 수 있음 |
| 카테고리·소유자·날짜가 바뀌어 병합 대상 경로 변경 | 새 위치로 복사할 수 있으며 이전 복사본을 자동 이동·삭제하지 않음 |
| 같은 이름이지만 파일 내용이 다름 | `_중복` 등의 새 이름으로 보존하므로 용량 증가 |
| 복원한 managed를 별도 원본 소스로 등록·재스캔 | 기존 복원 DB를 그대로 사용하는 절차와 다름. 불필요한 중복 등록을 피할 것 |

복원 파일을 확인했다고 해서 유일한 백업 ZIP을 바로 삭제하는 것은 권장하지 않습니다. 필요하면 다른 저장장치로 옮겨 복원된 데이터와 별도로 보관하세요.

## 12. Windows PowerShell 예제

예제에서는 `E:/photo_db`가 기존 DB, `E:/`가 허용 루트, `F:/backups`가 백업 저장소입니다. 실제 managed 위치는 DB 설정에서 읽습니다. 아래 Python 가상환경이 준비되어 있다고 가정합니다.

```powershell
# ZIP 백업
.\apps\photo_browser\.venv\Scripts\python.exe apps/photo_browser/cli.py --db E:/photo_db --root E:/ backup --destination F:/backups/photo-library-20261022.zip

# 검증
.\apps\photo_browser\.venv\Scripts\python.exe apps/photo_browser/cli.py backup-check --backup F:/backups/photo-library-20261022.zip

# 새 경로로 복원. E:/restored-photos는 존재하지 않아야 함
.\apps\photo_browser\.venv\Scripts\python.exe apps/photo_browser/cli.py restore --backup F:/backups/photo-library-20261022.zip --destination E:/restored-photos

# 복원한 DB로 실행
.\apps\photo_browser\.venv\Scripts\python.exe apps/photo_browser/app.py --root E:/restored-photos --db E:/restored-photos/db --directory E:/restored-photos/managed
```

## 13. 폴더 형식으로 백업하기

압축하지 않는 디렉토리 백업도 사용할 수 있습니다. 아래 백업 디렉토리는 미리 만들지 않습니다.

```bash
apps/photo_browser/.venv/bin/python apps/photo_browser/cli.py \
  --db /data/photo-library/db --root /data \
  backup --format directory --destination /backup/photo-library-20261022

apps/photo_browser/.venv/bin/python apps/photo_browser/cli.py \
  backup-check --backup /backup/photo-library-20261022

apps/photo_browser/.venv/bin/python apps/photo_browser/cli.py \
  restore --backup /backup/photo-library-20261022 \
  --destination /data/restored-photos
```

복원 경로 갱신과 원본 소스 제외 등의 원칙은 ZIP과 같습니다.

## 14. 용량 검사·검증·실패 처리

- 폴더 백업은 복사할 파일 총량에 16 MiB 여유분을 더해 시작 전 공간을 검사합니다.
- ZIP 백업은 압축 전 총량에 파일별 부가 정보·여유분을 더해 보수적으로 시작 전 공간을 검사하고, 압축 중에도 공간을 확인합니다. 압축이 잘 될 것을 전제로 부족한 디스크에서 시작하지 않습니다.
- 복원은 압축 전 총량에 16 MiB 여유분을 더해 시작 전 검사합니다. 복원할 DB의 경로 갱신과 파일시스템 부가 공간도 필요하므로 더 넉넉한 공간을 준비하세요.
- 이 검사는 다른 프로세스의 디스크 사용량을 예약하지 않습니다. 실행 중 다른 작업이 공간을 소비하면 오류가 발생할 수 있습니다. 백업 용량 검사는 스캔의 `scan_min_free_mb` 설정과 별도입니다.
- ZIP은 파일 내용을 블록 단위로 읽고 쓰며 별도의 전체 압축 해제 사본을 먼저 만들지 않습니다. 다만 파일 목록과 DB 메타데이터 처리에는 메모리가 필요합니다.
- 파일별 크기·SHA-256과 파일 목록을 검사합니다. 백업 중 파일 목록·수정 상태가 바뀌면 실패합니다. 등록된 사용 가능 관리 복사본이 실제로 없거나 스캔 정보와 다르면 실패합니다.
- ZIP에서 경로 이탈, 중복 파일 경로, 링크·특수 파일·암호화 항목, manifest와 실제 목록 불일치를 거부합니다. 앱에서 생성한 백업 ZIP을 사용하세요. manifest 크기 한도는 64 MiB입니다.
- 오류나 일반 중단 시 이번에 생성한 출력 파일/폴더를 정리하며 기존 백업과 원본 라이브러리는 보존합니다.
- 프로세스 강제 종료·전원 장애 시 미완성 ZIP/폴더가 남을 수 있습니다. **백업·복원 이어하기는 지원하지 않으므로 새 경로로 재실행**하세요.
- CLI 종료 코드는 정상 `0`, 검증·복사 등의 오류 `1`, `Ctrl+C` 중단 `130`입니다. CLI가 성공 결과를 반환하고 검증도 통과한 백업을 사용하세요.

## 15. 문제 해결

| 증상 | 확인과 조치 |
| --- | --- |
| 설정 DB가 없다는 오류 | 서버와 동일한 `--db`를 지정했는지 확인 |
| 허용된 루트 밖이라는 오류 | 기존 서버의 DB·managed를 포함하는 `--root`로 백업 실행 |
| 다른 작업이 실행 중이라는 오류 | 스캔·병합 등을 종료하고 서버와 외부 변경 작업 중지 |
| 대상이 이미 존재한다는 오류 | 새 ZIP 이름 또는 존재하지 않는 새 디렉토리 사용 |
| 공간 부족 | ZIP은 실제 압축 후 크기만으로 공간을 판단하지 않음. 압축 전 총량과 여유분 확보 |
| 심볼릭 링크 오류 | 실제 DB·managed 파일 구성을 확인. 링크의 외부 대상은 자동 수집하지 않음 |
| 관리 복사본 누락·손상 | 원본을 연결하고 라이브러리 상태와 병합 결과를 확인한 뒤 새 백업 생성 |
| 백업 무결성 오류 | 전송한 전체 파일을 확인. 원래 백업에서도 실패하면 정상 라이브러리에서 다시 백업 |
| 복원 후 사진이 안 열림 | `restore.json`의 DB·managed 경로로 실행했는지, 관리 복사본 누락 수가 있는지 확인 |
| 복원 후 원본 스캔 실패 | 이전 소스 경로·원격 인증은 별도 재연결 필요 |
| 과거 보고서에 옛 경로가 표시됨 | HTML 보고서와 일반 텍스트 히스토리는 원래 기록을 유지하는 동작 |

## 16. 현재 지원하지 않는 기능

- 원본 소스 파일을 함께 수집하는 백업 옵션 및 원본 폴더 구조 재생성
- 증분·차등 백업, 자동 스케줄, 오래된 백업 자동 정리
- 백업·복원의 중지 지점 이어하기
- 암호화 ZIP 생성·복원, 분할 ZIP 생성
- 파일 소유권·ACL·생성 시각·모든 빈 폴더의 완전한 보존
- 서로 다른 파일시스템의 파일명 제한까지 자동 변환하는 기능

SHA-256은 파일 누락·손상 확인용이며 암호화나 전자서명은 아닙니다. 백업에는 사진과 전체 DB의 개인 정보·경로·기록이 포함되므로 접근 가능한 사람과 저장 위치를 관리해야 합니다. 원본 소스와 인증 값은 필요에 따라 별도로 보존하세요.
