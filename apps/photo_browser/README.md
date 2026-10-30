# BerePi Photo Browser

사진·동영상을 스캔하여 JSON으로 등록하고, 월별 병합 복사·이벤트/태그 편집·검색·휴지통 복원을 제공하는 앱입니다. 기존 폴더 탐색 화면도 유지합니다.

웹페이지 맨 위에는 **서버 내부 IP와 외부 IP**를 표시합니다. 내부 IP는 서버의 호스트 이름과 기본 네트워크 경로에서 감지한 주소이며, 여러 주소가 있으면 함께 표시합니다. 외부 IP는 서버에서 HTTPS `https://api.ipify.org`를 조회한 공인 IP입니다. 접속한 브라우저의 IP가 아닙니다. NAT·VPN·프록시 환경에서는 인터넷 통신에 사용되는 출구 IP가 표시되며, 해당 주소로 외부에서 접속할 수 있다는 의미는 아닙니다.

IP 조회는 페이지 표시 후 백그라운드에서 실행합니다. 외부 조회 타임아웃은 4초이고, 성공 결과는 10분 동안 캐시하며 실패 시 1분 뒤 재시도합니다. 화면은 조회 중에는 약 1초, 이후에는 약 1분 간격으로 상태를 확인합니다. 인터넷 연결이나 조회 서비스에 문제가 있으면 외부 IP를 `조회 불가`로 표시하고 나머지 앱 기능은 계속 사용할 수 있습니다. 주소 조회 API는 `GET /api/server-network`이며 기존 앱 인증 설정을 따릅니다.

지원 형식은 사진 **JPG/JPEG, PNG, GIF, WebP**, 동영상 **MP4, MOV, AVI**입니다. 기존 폴더 탐색과 라이브러리 소스 스캔·DB 등록·병합 복사에 동일하게 적용되며 확장자 대소문자는 구분하지 않습니다. 동영상 메타데이터 추출에는 `ffprobe`가 필요합니다. 웹 화면의 동영상 재생 가능 여부는 브라우저와 파일의 코덱에 따라 달라지며, 앱은 재생용 형식 변환을 수행하지 않습니다.

## 구성과 처리 흐름

```text
로컬 / WebDAV / HTTP 목록
  → 파일 목록 집계 → 메타데이터·SHA-256 분석 → 월별 JSON 발행
  → 월별 병합 미리보기 → 검증 후 복사
  → 이벤트·태그·사람 지정 → 검색·브라우징
  → 휴지통 이동 → 복원 또는 확인 후 영구 삭제
```

스캔·JSON 생성과 실제 병합 복사는 각각 중지 후 이어하기를 지원합니다. 스캔만 실행하면 사진을 복사하지 않으며, 관리 디렉토리에 모으려면 별도로 병합 복사를 실행해야 합니다.

| 파일 | 역할 |
| --- | --- |
| `app.py` | 서버 실행, 기존 폴더 탐색 및 미디어 제공 |
| `library.py` | JSON 저장, 메타데이터, 원격 접근, 병합, 휴지통·복원 |
| `merge_history.py` | 병합 전후 디렉토리 집계, 실행별 JSON·HTML 보고서 |
| `scan_engine.py` | 전체 목록 집계, 진행률, 체크포인트, 중지·이어하기, 용량 검사 |
| `backup.py` | DB·관리 파일 폴더/ZIP 백업, 해시 검증, 새 경로 복원 |
| `analysis_skills.py` | 사진·문서 페르소나, 프롬프트 생성, 유형별 응답 검증·저장 |
| `library_api.py` | 라이브러리 API, 백그라운드 작업, 인증·변경 요청 검사 |
| `templates/index.html` | 화면 구성 |
| `static/library.js` | 라이브러리·설정·진행률·휴지통 화면 동작 |
| `static/app.js` | 기존 폴더 탐색 화면 동작 |
| `config.example.json` | 로컬·WebDAV 설정 예시 |

## 목차

- [설치 및 실행](#설치-및-실행)
- [라이브러리 사용 순서](#라이브러리-사용-순서)
- [사진·명함·견적서 분석 Skill](#사진명함견적서-분석-skill)
- [병합 결과 백업과 다른 장치로 이전](#병합-결과-백업과-다른-장치로-이전)
- [백업·복원 상세 가이드](backup_restore.md)
- [지능형 갤러리 설계: 태그 관리·Gemma 설명·검색](intelligent_photo_gallery_design.md)
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

### 여러 디렉토리를 통합 소스로 지정

`--directory`를 여러 번 지정하면 각 디렉토리를 같은 JSON DB의 소스로 등록합니다.
첫 번째 디렉토리는 기존 폴더 탐색의 시작 경로가 됩니다.

```bash
apps/photo_browser/.venv/bin/python apps/photo_browser/app.py \
  --root /data --db /data/photo_db \
  --directory /data/photos --directory /data/phone --directory /data/camera
```

실행 시 여러 소스의 사진·동영상이 하나의 라이브러리로 통합된다는 안내와 함께,
디렉토리마다 다음 정보를 터미널에 출력합니다.

- `[기존 등록]` 또는 `[신규 추가]`: 현재 DB의 소스 설정 기준으로 구분합니다.
- 경로, 소스 ID, 하위 폴더 포함 여부
- 지원 미디어 파일 수, 사진·동영상별 개수, 총 용량
- 이전 스캔 상태·처리 개수·DB 반영 여부 또는 스캔 기록 없음
- 전체 소스의 파일 수·용량 합계와 집계 오류

기존 소스의 ID·분류·소유자·재귀 설정은 유지합니다. 새 소스는 경로를 기반으로 생성한
ID와 `family` 분류, `default` 소유자, 하위 폴더 포함 설정으로 저장합니다.
같은 경로를 반복 지정하면 한 번만 등록하며, 다른 기존 소스도 유지합니다.
모든 입력 경로는 존재하는 디렉토리이고 `--root` 안에 있어야 합니다.
DB나 관리 디렉토리 및 그 하위 폴더는 소스로 지정할 수 없습니다.

집계는 지원 미디어를 대상으로 하며, 심볼릭 링크·DB·관리 디렉토리 내부는 제외합니다.
기존 소스에 하위 폴더 제외 설정이 있으면 해당 설정대로 집계합니다.
읽기 오류가 발생하면 불완전한 집계라고 표시합니다. 큰 디렉토리는 시작 시 집계에 시간이 걸릴 수 있습니다.
합계는 중복 제거 전 소스별 수치로, 상하위 소스 경로가 겹치면 같은 파일이 중복 집계될 수 있습니다.

**소스 등록은 스캔·병합 완료를 의미하지 않습니다.** 시작 시에는 등록과 용량 집계만 수행하며,
웹의 `소스·스캔·병합`에서 각 소스를 스캔하면 통합 라이브러리에 등록됩니다.
그다음 병합을 실행하면 관리 디렉토리로 복사합니다.
`--directory` 하나만 지정하거나 생략하면 기존처럼 탐색 시작 폴더만 설정합니다.

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

### 가로 단계 진행 표시

화면 상단의 **사진 병합 단계**에서 다음 네 단계를 가로로 확인할 수 있습니다. 작은 화면에서는 단계 목록을 좌우로 스크롤하세요. 단계 버튼을 누르면 해당 설정·작업 위치로 이동하며 작업을 자동 실행하지는 않습니다.

| 단계 | 완료 판정과 표시 |
| --- | --- |
| 1. ID·소스 설정 | 소스 ID·카테고리·소유자와 관리 루트 설정 확인. 기본 분류·소유자 값도 유효한 설정으로 사용 |
| 2. 스캔·JSON 생성 | 현재 설정에 맞는 모든 등록 소스의 목록 집계·파일 처리가 오류 없이 완료되어야 완료. 소스별 완료 수와 파일 처리 수·백분율 표시 |
| 3. DB 구성·반영 | 해당 스캔의 월별 JSON·`index.json` 발행이 모두 끝나야 완료. 스캔 후 자동으로 수행되며 별도의 DB 생성 버튼은 없음 |
| 4. 관리 디렉토리 병합 | 현재 활성 항목 모두에 현재 분류/소유자/연월 경로의 사용 가능한 관리 복사본이 DB에 등록되어야 완료. 복사 수와 등록 수 표시 |

색상은 **초록=완료, 파랑=진행 중, 주황=확인 필요, 빨강=실패, 회색=대기**입니다. 색상 외에도 기호·상태 문구를 함께 표시합니다. 목록 집계와 DB 발행처럼 정확한 비율이 없는 동안은 미확정 진행 막대를 표시합니다. 일부 파일 오류, 중지, 공간 부족은 전체 완료로 표시하지 않으며 기존 작업 내역에서 원인과 이어하기를 확인할 수 있습니다. 활성 파일이 없는 경우에는 병합할 대상이 없다는 안내를 표시합니다.

설정·스캔 체크포인트·현재 JSON 카탈로그·병합 작업 기록을 읽어 약 **2초마다** 갱신하므로 새로고침 후에도 상태를 복원합니다. CLI에서 끝낸 스캔·병합 기록도 반영합니다. 소스 추가·변경, 재스캔, 분류 경로 변경 시 필요한 단계가 다시 대기/확인 상태로 계산됩니다. 웹서버 재시작으로 중단된 웹 작업은 중단 상태로 표시하며, CLI 강제 종료 시에는 마지막 저장 상태가 남을 수 있습니다.

전체 퍼센트는 각 단계를 같은 비중으로 계산한 **단계 기준 진행률**이며 남은 시간 예측이 아닙니다. 병합 완료 역시 **DB에 등록된 복사 상태** 기준으로, 폴링마다 모든 파일을 다시 읽어 무결성을 검사하지 않습니다. 실제 파일 누락·내용 확인은 정밀 파일 확인 또는 CLI `compare`로 수행하세요. 네트워크·조회 오류가 나면 이전 표시가 최신이 아닐 수 있다는 경고를 보여줍니다.

`GET /api/workflow`는 `steps`, `completed_steps`, `total_steps`, `percent`, `note`를 반환하며 기존 인증과 `Cache-Control: no-store`를 적용합니다. 상태 조회는 사진이나 DB를 변경하지 않습니다. 카탈로그와 병합 세션 집계는 변경된 세대·기록만 다시 읽어 반복 조회 비용을 줄입니다.

### 사진·동영상 다운로드

라이브러리 갤러리의 체크박스로 파일을 선택하고 **선택 파일 다운로드**를 누릅니다. 한 개는 원래 이름의 개별 파일로, 여러 개는 ZIP으로 내려받습니다. 현재 페이지 전체 선택을 사용할 수 있으며 한 번에 최대 100개를 지원합니다. 상세 미리보기의 **이 파일 다운로드**로도 받을 수 있습니다. 페이지·필터 변경 시 선택은 기존 방식대로 초기화됩니다.

ZIP은 서버의 백그라운드 워커가 `db/downloads` 아래에 생성하므로 다른 작업이 있으면 대기합니다. 준비 후 브라우저의 기본 다운로드로 전송하며 전체 ZIP을 브라우저 메모리에 미리 올리지 않습니다. 사진·동영상은 재압축하지 않고 원본 바이트로 보존하며, ZIP 안에서 이름이 겹치면 `_중복`, `_중복_2`로 구분합니다. 관리 복사본이 있으면 우선 사용하고 없으면 등록된 원본에서 읽습니다. 원격 파일도 지원하며 ZIP 준비 중 크기·SHA-256이 스캔 정보와 다르면 오류로 중단하고 재스캔을 안내합니다. 일부 파일을 조용히 누락한 ZIP은 제공하지 않습니다.

다운로드 링크는 준비 완료 후 **1시간** 유효하며 작업 내역 카드에서도 다시 받을 수 있습니다. 만료된 ZIP과 메타데이터는 다음 ZIP 준비·만료 링크 조회 시 정리하며, 유휴 상태에서 정기 삭제하는 기능은 아닙니다. ZIP 디스크 공간은 기본 `scan_min_free_mb` 여유 기준과 선택 파일 용량을 고려하고, 원격 임시 다운로드 디스크도 검사합니다. 디스크 부족·파일 누락·준비 오류 시 임시 ZIP은 제거하며 원본과 분류 정보는 변경하지 않습니다. ZIP 파일은 DB 백업에 꼭 포함할 필요가 없습니다. 이미 준비된 ZIP은 원본의 휴지통 이동과 별개로 만료 시까지 유지됩니다.

### 파일 업로드

상단 **파일 업로드** 탭에서 웹서버의 저장 디렉토리를 입력하고 사진·동영상 파일을 선택한 뒤 **업로드 시작**을 누르세요. **현재 탐색 경로 사용**으로 현재 경로 설정 값을 가져올 수 있습니다. 저장 위치는 `--root` 안의 **로컬/마운트 디렉토리**여야 합니다. 없는 경로를 입력한 경우 **디렉토리 생성**을 누르면 필요한 상위 폴더까지 함께 만듭니다. 생성한 경로는 업로드 저장 위치에 자동으로 적용되고, **저장 폴더 탐색**으로 바로 열 수 있습니다. 이미 있는 디렉토리는 그대로 사용하며, 같은 경로에 파일이 있으면 오류를 표시하고 보존합니다. 업로드 중에는 디렉토리 생성 버튼을 사용할 수 없습니다. 브라우저가 있는 컴퓨터의 파일을 서버로 전송하며 원격 HTTP/WebDAV URL로 직접 업로드하지는 않습니다.

- 한 번에 최대 **100개**를 순서대로 전송합니다. 현재 파일의 바이트 진행률과 각 파일의 성공·실패·미전송 상태를 표시합니다.
- 기본 파일당 한도는 **4096 MiB (4 GiB)**입니다. 서버 시작 전 `PHOTO_BROWSER_UPLOAD_MAX_MB` 환경변수를 1 이상의 정수로 지정해 변경할 수 있습니다. 예: PowerShell `$env:PHOTO_BROWSER_UPLOAD_MAX_MB='8192'`, Linux `export PHOTO_BROWSER_UPLOAD_MAX_MB=8192`. 서버 재시작 후 적용됩니다. 일반 JSON API 요청 한도는 기존 **2 MiB**를 유지합니다. Flask **3.1 이상**이 필요하므로 변경된 `requirements.txt`로 의존성을 갱신하세요.
- 지원 확장자는 `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.mp4`, `.mov`, `.avi`입니다. 확장자와 빈 파일 여부를 검사하며 파일 내용의 디코딩 검증은 하지 않습니다.
- 파일 이름이 겹치면 `_중복`, `_중복_2` 등을 붙여 모두 보존합니다. 같은 내용이라도 업로드 시에는 별도 파일로 저장하며 기존 파일을 덮어쓰지 않습니다. 파일명에 사용할 수 없는 문자는 정리합니다. 브라우저가 제공하는 원본 수정 시각을 유지해 기존 폴더 탐색의 날짜 그룹에도 반영합니다.
- 임시 파일에 블록 단위로 저장하고 전송이 완료된 후 최종 이름으로 공개합니다. 같은 디렉토리 내 하드 링크 생성을 지원하는 저장소가 필요하며, 지원하지 않거나 권한이 없으면 해당 파일을 오류로 표시합니다. 설정의 `scan_min_free_mb`를 안전 여유 공간으로 사용하며, 전송 전 남은 파일 용량과 전송 중 디스크 여유 공간을 검사합니다. 전송 실패·연결 끊김·용량 부족 시 임시 파일을 정리합니다. 서버 프로세스 강제 종료 시 남은 `.photo-upload-*.part`는 완성된 사진으로 표시되지 않으며, 실행 중인 업로드가 없는지 확인한 뒤 정리할 수 있습니다.
- **현재 파일 완료 후 중지**는 현재 전송·저장을 마친 뒤 나머지 파일을 전송하지 않습니다. 성공한 파일은 그대로 남습니다. 재시도할 때 실패·미전송 파일만 다시 선택하세요. 연결이 끊긴 경우에는 서버 저장 여부가 불확실할 수 있으므로 저장 폴더를 먼저 확인하세요.

완료 후 **저장 폴더 탐색**으로 업로드한 사진을 확인할 수 있습니다. 업로드 자체는 라이브러리 JSON을 생성하지 않습니다. 이벤트·태그로 관리하려면 해당 폴더를 소스로 등록하고 **스캔 / JSON 생성**을 실행하세요.

디렉토리 생성은 `POST /api/uploads/directory`에 JSON `{"directory":"서버 경로"}`와 `X-Photo-Browser: 1` 헤더를 전송합니다. 생성 시 201, 기존 폴더이면 200과 `directory`, `created`를 반환합니다. 허용된 루트 밖의 경로는 거부하며, 쓰기 권한 오류는 409로 응답합니다.

업로드 설정은 `GET /api/uploads/settings`, 업로드는 `POST /api/uploads?directory=<서버 디렉토리>&name=<파일명>&modified=<원본 수정 Unix 밀리초>`를 사용합니다. 요청 본문에는 **파일 1개의 원본 바이트**를 넣고 `Content-Type: application/octet-stream`, `X-Photo-Browser: 1`을 지정합니다. `modified`는 선택 항목입니다. 성공 시 HTTP 201과 저장 경로·파일명·크기·SHA-256·이름 변경 여부를 반환합니다. 기존 인증과 Origin 검사를 적용하며, 크기 초과는 413, 디스크 공간 부족은 507로 응답합니다. 리버스 프록시에서도 큰 요청을 허용하고 전송 시간 제한을 맞춰야 합니다. Apache/Nginx 등 앞단에서 차단하면 앱에 도달하기 전에 실패할 수 있습니다.

**기존 폴더 탐색에서도 다운로드할 수 있습니다.** 스캔 시작으로 폴더를 조회한 다음 사진·동영상 카드의 체크박스를 선택하고 **선택 파일 다운로드**를 누르세요. 1개는 원본 파일, 여러 개는 ZIP으로 받습니다. **표시된 파일 선택**은 현재 화면에 표시한 파일 중 앞의 최대 100개를 선택합니다. 미리보기의 **이 파일 다운로드**로도 개별 원본을 받을 수 있습니다. 폴더·날짜·형식 변경 또는 다음 파일 불러오기로 결과를 다시 조회하면 선택은 초기화됩니다. 불러온 결과를 100개 더 표시할 때는 기존 선택을 유지합니다.

라이브러리 등록이나 JSON 스캔 저장 없이 현재 허용된 루트 안의 파일을 읽습니다. ZIP은 기존 라이브러리 다운로드와 동일하게 중복 이름 보존, 디스크 공간 검사, 작업 진행 표시, 1시간 유효 링크를 적용합니다. 폴더 파일에는 저장된 SHA-256이 없으므로 요청 시 파일 크기·수정 시각·파일 식별 정보를 기록하고 ZIP 준비 전후에 변경 여부를 확인합니다. 파일 누락·변경 시 전체 ZIP 준비가 실패하며 원본은 변경하지 않습니다. 개별 수신은 `GET /media?path=<경로>&download=1`, ZIP 준비는 `POST /api/folder-downloads`에 `{"paths":["절대경로1","절대경로2"]}`를 전송하며 `job_id`로 진행 상태를 조회합니다.

개별 파일은 `GET /api/library/<media_id>/file?download=1`, ZIP 준비는 `POST /api/downloads`에 `{"ids":["미디어ID1","미디어ID2"]}`, ZIP 수신은 `GET /api/downloads/<download_id>`를 사용합니다. ZIP 준비 응답은 `job_id`를 반환하고 기존 작업 조회 API로 상태를 확인합니다. 모든 요청은 앱의 기존 인증과 로컬·원격 경로 제한을 따릅니다. 휴지통·영구 삭제 항목은 새 다운로드 준비 대상에서 제외됩니다.

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

`--db`를 생략하면 `PHOTO_BROWSER_DB`, 환경변수도 없으면 `apps/photo_browser/db`를 사용합니다. 기존 설정이 없는 DB는 오류로 처리합니다. 원격 병합에는 서버와 같은 인증 환경변수를 설정해야 합니다. 병합은 동기 실행되며 종료할 때 결과와 `merge_id`를 출력합니다. `Ctrl+C`는 현재 파일 처리 후 중지 상태를 저장합니다. 중지·복사 오류는 종료 코드 1, 정상 완료와 조회는 0을 반환합니다. 원본은 유지하며 기존 대상 파일의 내용이 다르면 `_중복`, `_중복_2` 등의 이름으로 별도 복사합니다. 서버가 실행 중이어도 사용할 수 있지만 다른 쓰기 작업과 겹치면 기존 DB 잠금에 의해 거부됩니다.

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

촬영 날짜가 없는 파일은 연도와 월에 `unknown/unknown`을 사용합니다. 병합은 여러 사진을 한 파일로 합치는 작업이 아니라, 원본 파일을 유지하면서 위 폴더 구조에 복사하는 작업입니다. 같은 DB와 관리 디렉토리를 유지하면 첫 번째 소스 병합 후 두 번째 소스를 병합해도 결과가 같은 라이브러리에 누적됩니다. 대상 경로에 같은 내용(SHA-256)의 파일이 있으면 재사용합니다. 내용이 다르면 기존 파일을 덮어쓰지 않고 `사진_중복.jpg`, `사진_중복_2.jpg`처럼 접미사와 번호를 붙여 모두 보존합니다. 이름 충돌을 해결한 항목은 정상 복사로 기록하며, 실제 읽기·쓰기·검증 실패만 오류로 기록합니다.

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
  reports/merges/<UTC시각>_<보고서ID>.json          # 상세 병합 보고서
  reports/merges/<UTC시각>_<보고서ID>.html          # 사람이 읽는 보고서
  reports/merges/<UTC시각>_<보고서ID>.summary.json  # 웹 목록용 요약
  jobs/<작업ID>.json
  trash/<휴지통ID>.json
  cache/                          # 원격 미리보기 캐시

관리 디렉토리/
  family/person001/2026/10/사진.jpg
  family/person001/2026/10/사진_중복.jpg
  .trash/<휴지통ID>/family/person001/2026/10/사진.jpg
```

각 미디어에는 고유 `media_id`, 이벤트 이름 목록(`classification.events`), 태그, 사람 ID, 촬영 정보, 파일 크기, SHA-256, 원본과 관리 복사본 목록(`locations`), 검증 결과, 삭제 상태를 기록합니다. 각 물리적 원본은 별도 항목으로 추적하며, 동일 내용은 중복 그룹으로 연결합니다. 같은 월·분류·소유자의 동일 파일명 후보에서 SHA-256이 같으면 관리 복사본을 재사용합니다. 원본 파일명을 우선 사용하고, 다른 내용의 파일과 이름이 겹치면 `_중복`, `_중복_2` 등의 접미사를 확장자 앞에 붙입니다. 원래 이름은 JSON의 `name`에 유지하며 실제 저장 위치는 `locations`에 기록합니다.

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

## 사진·명함·견적서 분석 Skill

명함·견적서도 지원 이미지로 업로드·스캔·병합한 뒤 목적에 맞는 페르소나를 적용할 수 있습니다. 현재 구현은 **프로필 선택 → 프롬프트/요청 생성 → 별도로 얻은 모델 응답 검증·저장**입니다. LLM 서버 자동 호출·인증·분석 워커와 설명 검색은 후속 연결 대상입니다. 프로필 선택으로 외부에 이미지를 자동 전송하지 않으며 PDF·동영상·여러 페이지 문서 통합은 지원하지 않습니다.

### 페르소나와 어댑터

| Skill ID | 역할 | 유형별 추출 정보 |
| --- | --- | --- |
| `photo_docent` | 갤러리 도슨트 | 장면, 보이는 인물 묘사, 위치 묘사 |
| `business_card` | 명함 기록 담당자 | 이름, 회사, 부서, 직책, 전화, 이메일, 웹사이트, 주소 |
| `quotation` | 구매 검토 담당자 | 공급자·수신자, 견적번호, 발행일·유효기한, 품목·수량·단가, 세금·합계, 결제 조건 |
| `document` | 일반 문서 기록 담당자 | 문서 종류, 문서에 적힌 날짜, 핵심 사항 |

**Skill 프로필**은 역할·목표·추가 지침·버전을, **문서 유형 어댑터**는 추출 규칙과 JSON Schema를 담당합니다. 서로 다른 구매팀 페르소나를 같은 `quotation` 어댑터에 연결하는 방식으로 확장합니다. 모델 서버별 전송은 별도 레이어로 연결해야 합니다.

공통 응답 필드는 `title`, `description`, `suggested_tags`, `ocr_text`, `warnings`, `extracted`이며 마지막 필드만 유형별 구조가 다릅니다. 알 수 없는 추출값은 규격에 따라 `null` 또는 빈 배열로 남깁니다. 금액·수량은 `₩1,234,500`, `1` 같은 문자열로 보존하고 자동 합산이나 세금 추정을 하지 않습니다. 문서 발행일과 사진 촬영일도 구분합니다. 스키마 검증이 내용의 정확성까지 보장하지 않으므로 결과는 `unreviewed`로 저장합니다.

### 웹 사용 순서

1. 라이브러리에서 이미지 한 개를 선택하고 **분석 Skill · 사진/명함/견적서**를 누릅니다.
2. 프로필, 모델 이름, 추가 요청을 입력하고 **프롬프트 준비**를 누릅니다.
3. 이미지 해시를 확인한 뒤 역할별 `system`, 입력 문맥 `prompt`, 출력 `format`을 표시합니다. 이 미리보기의 `images`는 비어 있습니다. 모델을 별도로 사용할 때는 해당 이미지도 함께 첨부하세요.
4. 모델이 반환한 **결과 객체 JSON만** 붙여넣고 **응답 검증·저장**을 누릅니다. 서버가 `response` 안에 JSON 문자열을 반환했다면 그 문자열 안의 객체를 사용합니다.
5. 기존 분석 결과에서 프로필·시각·검토 상태·오래된 결과(`stale`)를 확인합니다.

동일 해시의 관리 복사본을 우선 사용하므로 원본이 오프라인이어도 준비할 수 있습니다. JPEG·PNG·WebP·GIF를 지원하고 이미지당 20 MiB, 응답당 256 KiB로 제한합니다. 실제 모델의 이미지 형식 지원 여부는 별도로 확인하세요.

### CLI와 사용자 페르소나 등록

```bash
python3 apps/photo_browser/cli.py --db /data/photo_db --root /data skills

# 예제 JSON을 복사해 역할·목표·지침을 편집한 뒤 등록
python3 apps/photo_browser/cli.py --db /data/photo_db --root /data \
  skill-save --file apps/photo_browser/analysis_skill.example.json

# 프롬프트 미리보기 (기본 이미지 미포함)
python3 apps/photo_browser/cli.py --db /data/photo_db --root /data \
  analysis-prepare --media-id MEDIA_ID --skill business_card \
  --instruction '회사와 연락처를 중심으로 정리해 주세요.'

# 원본 이미지 Base64를 포함한 Ollama 호환 요청 내보내기 (호출 없음)
python3 apps/photo_browser/cli.py --db /data/photo_db --root /data \
  analysis-prepare --media-id MEDIA_ID --skill equipment_purchasing \
  --model gemma4:31b --include-image > prepared-request.json

# 별도로 모델을 호출해 받은 결과 객체를 검증·저장
python3 apps/photo_browser/cli.py --db /data/photo_db --root /data \
  analysis-save --request-id REQUEST_ID --file model-result.json
python3 apps/photo_browser/cli.py --db /data/photo_db --root /data \
  analysis-results --media-id MEDIA_ID
```

출력 묶음의 `request_id`를 응답 저장에 사용합니다. **모델 요청 본문은 묶음 내부의 `request` 객체**이며 `model`, `stream`, `system`, `prompt`, `format`, `images`를 포함합니다. 인증 게이트웨이가 Ollama와 같은 계약을 지원한다고 가정하지 마세요. 연동 요구사항은 [지능형 갤러리 설계](intelligent_photo_gallery_design.md)의 7장을 참고하세요.

[analysis_skill.example.json](analysis_skill.example.json)을 복사해 새로운 `skill_id`, `label`, `persona`, `objectives`, `instructions`를 지정하고 `adapter`는 위 4종 중에서 선택합니다. 기존 기본 Skill은 덮어쓸 수 없으며 사용자 Skill 변경 시 `version`을 높여야 합니다. 정의는 JSON 데이터로만 처리하고 사용자 Python·셸·도구 코드를 실행하지 않습니다. 사용자 프로필 등록은 현재 CLI에서 제공합니다.

### 저장 구조와 API

```text
db/ai/
  skills/<skill_id>.json                 사용자 페르소나
  requests/<request_id>.json             Skill·규격·모델·문맥 스냅샷
  runs/<media_id>/<run_id>.json          분석 결과와 입력 fingerprint
```

명시적 입력 문맥에는 현재 DB의 이벤트·태그·사람 ID와 스캔 당시 촬영 시각·날짜 근거를 넣습니다. 내부 경로·인증값·정확한 GPS는 넣지 않으며 사람 ID를 이름이나 얼굴과 자동 대응하지 않습니다. 이미지 속 글자·사용자 추가 요청은 시스템 지침과 분리해 데이터로 전달합니다. `--include-image` 출력에는 원본 이미지와 EXIF 개인정보가 포함될 수 있으므로 보관·전달 범위를 확인하세요. DB 요청 기록에는 Base64를 저장하지 않습니다.

분석은 사진 파일·촬영 시각·사용자 태그를 덮어쓰지 않으며 추천 태그도 자동 적용하지 않습니다. 사진 해시·태그·Skill·어댑터 계약이 바뀐 요청의 응답은 저장을 거부하고 이전 결과는 `stale: true`로 표시합니다. 한 사진에 여러 Skill의 결과를 보관할 수 있고 `db/ai`는 기존 전체 DB 백업·복원에 포함됩니다. 결과의 일반 검색·벡터 검색 연동은 아직 포함하지 않습니다.

| API | 동작 |
| --- | --- |
| `GET /api/analysis/skills` | 프로필과 출력 Schema 조회 |
| `POST /api/analysis/prepare` | `media_id`, `skill_id`, `instruction`, `model`로 준비. 웹 응답은 이미지 미포함 |
| `POST /api/analysis/results` | `request_id`, `result`로 응답 검증·저장 |
| `GET /api/analysis/<media_id>/results` | 결과 이력과 stale 상태 조회 |

기존 인증·변경 요청 헤더·Origin 검사와 DB 쓰기 잠금을 적용합니다.

## 병합 결과 백업과 다른 장치로 이전

백업 범위, 원본과 managed의 차이, DB 예제, ZIP 이전·복원 절차와 공간 사용에 대한 자세한 설명은 [백업·복원 상세 가이드](backup_restore.md)를 참고하세요.

CLI로 **JSON DB 전체와 관리 디렉토리 전체(휴지통 포함)**를 하나의 **ZIP 압축 파일 또는 백업 폴더**에 저장하고 다른 장치의 새 경로로 복원할 수 있습니다. 사진뿐 아니라 이벤트·태그·촬영 정보·병합 보고서·스캔 체크포인트도 함께 보존합니다. 일반 파일과 기존 캐시·다운로드 ZIP도 포함하며 `.write.lock` 파일은 제외합니다. 심볼릭 링크나 일반 파일이 아닌 항목은 오류로 처리합니다. 외장 디스크나 마운트된 NAS에 직접 저장하거나, 완성된 ZIP 파일/백업 폴더를 다른 장치로 복사할 수 있습니다. `.zip`으로 끝나는 대상은 자동으로 ZIP 압축을 사용하며, 그 외에는 기존 폴더 백업 형식을 유지합니다. `--format zip` 또는 `--format directory`로 명시할 수도 있습니다.

### ZIP 파일 하나로 다른 시스템에 이전하기

서버의 쓰기 작업을 중지하고, 아래 경로를 실제 설정으로 바꿔 저장소 루트에서 실행합니다. ZIP 경로는 DB·managed 및 원본 스캔 디렉토리 밖에 두고, 기존 파일이 없는 새 이름을 지정하세요.

```bash
# DB의 설정에서 managed 경로를 자동으로 읽어 ZIP에 함께 저장
python3 apps/photo_browser/cli.py --db /data/photo_db --root /data \
  backup --format zip --destination /backup/photo-library-20261022.zip

# 압축을 별도로 풀지 않고 파일 목록·크기·SHA-256 검증
python3 apps/photo_browser/cli.py backup-check --backup /backup/photo-library-20261022.zip

# ZIP 파일 하나를 새 장치에 복사
scp -p /backup/photo-library-20261022.zip user@new-host:/backup/

# 새 장치에서 다시 검증한 뒤 새 디렉토리에 복원
python3 apps/photo_browser/cli.py backup-check --backup /backup/photo-library-20261022.zip
python3 apps/photo_browser/cli.py restore \
  --backup /backup/photo-library-20261022.zip --destination /data/restored-photos

# 복원 결과의 새 DB·managed 경로로 실행
python3 apps/photo_browser/app.py --root /data/restored-photos \
  --directory /data/restored-photos/managed --db /data/restored-photos/db
```

PowerShell에서는 설치한 가상환경의 Python을 사용합니다. 예시 경로를 실제 경로로 바꾸세요.

```powershell
.\apps\photo_browser\.venv\Scripts\python.exe apps/photo_browser/cli.py --db E:/photo_db --root E:/ backup --destination F:/backups/photo-library-20261022.zip
.\apps\photo_browser\.venv\Scripts\python.exe apps/photo_browser/cli.py backup-check --backup F:/backups/photo-library-20261022.zip
.\apps\photo_browser\.venv\Scripts\python.exe apps/photo_browser/cli.py restore --backup F:/backups/photo-library-20261022.zip --destination E:/restored-photos
```

ZIP에는 `manifest.json`, `db/`, `managed/`가 들어갑니다. manifest에는 **원래 DB 경로·managed 경로·허용 루트·원본 소스 위치**, 백업 시간, 파일별 상대 경로·크기·수정 시각·SHA-256을 기록합니다. 원격 인증 비밀번호/환경변수는 새로 수집하지 않습니다. DB 안의 기존 설정·기록은 그대로 포함됩니다. 복원 시 DB와 managed 참조를 새 경로로 연결하며, 원본 소스 위치는 원래 값을 유지합니다.

ZIP은 ZIP64와 무손실 DEFLATE 압축을 사용하며, 사진을 재인코딩하지 않습니다. 이미 압축된 사진·동영상은 용량 감소가 작을 수 있습니다. 결과의 `total_bytes`는 원본 파일 합계, `archive_bytes`는 실제 ZIP 크기입니다. 큰 원본을 메모리에 모두 올리거나 별도 전체 사본을 만들지 않고 블록 단위로 압축·검증·복원합니다. 생성 완료 후 ZIP을 다시 열어 SHA-256을 검증한 다음 성공을 반환합니다. 복원 시 원본 수정 시각을 manifest에서 읽어 적용합니다. 일반 압축 해제만으로는 DB 내부 경로를 갱신할 수 없으므로 앱의 `restore` 명령을 사용하세요.

앱에서 생성한 ZIP만 지원합니다. 암호화 ZIP, 링크·특수 파일, 중복 경로, manifest에 없는 파일, 경로 이탈 항목은 거부합니다. manifest 크기 한도는 64 MiB입니다. ZIP 생성 전에는 압축 전 파일 총량에 여유분을 더한 공간을 보수적으로 요구하고, 압축 중에도 디스크 공간을 확인합니다. 복원에는 압축 해제 후 크기에 해당하는 공간이 필요합니다. 오류·일반 중단 시 이번에 생성한 ZIP 또는 복원 폴더를 제거하며 기존 백업을 덮어쓰지 않습니다. 강제 종료로 남은 미완성 ZIP은 이어쓰지 않고 새 이름으로 다시 생성하세요. **원본 소스 파일은 ZIP에도 포함하지 않으므로 관리 복사본 누락 수가 0인지 확인하세요.**

아래는 압축하지 않는 폴더 형식의 백업·이전 절차입니다.

### 1. 백업 전 준비

아래 명령은 저장소 루트에서 실행합니다. 설치한 Python 가상환경을 사용하고 예시 경로는 실제 서버 설정으로 바꾸세요. 기존 장치의 DB는 `/data/photo_db`, 허용 루트는 `/data`, 백업 저장소는 `/backup`인 예입니다.

1. 필요한 사진의 스캔과 병합을 완료합니다. 실행 중인 작업은 **중지하고 저장** 후 종료 상태를 확인합니다.
2. 일관된 백업을 위해 웹서버와 외부 파일 변경 작업을 중지합니다. 서버를 켠 상태도 지원하지만 다른 쓰기 작업과 충돌하면 백업이 거부됩니다.
3. `/backup` 상위 경로를 준비하고 쓰기 권한·여유 공간을 확인합니다. DB와 관리 파일의 복사량 외에도 여유 공간이 필요합니다.
4. 백업 대상 `/backup/photo-library-20261022`는 미리 만들지 않습니다. 실행마다 날짜나 번호가 다른 새 경로를 사용하세요.

### 2. 기존 장치에서 백업 생성

```bash
python3 apps/photo_browser/cli.py --db /data/photo_db --root /data \
  backup --destination /backup/photo-library-20261022
```

반환 JSON에서 `status: "completed"`와 `active_items_without_managed_copy: 0`을 확인합니다. 후자가 0보다 크면 관리 복사본이 없는 사진이 있으므로 필요한 병합을 마친 뒤 다른 새 폴더로 백업하세요. 오류가 발생했다면 다음 단계로 진행하지 않습니다.

### 3. 백업 검증 후 다른 장치로 전송

```bash
python3 apps/photo_browser/cli.py backup-check --backup /backup/photo-library-20261022
```

`status: "verified"`와 파일 수·총 바이트를 확인합니다. `backup-check`는 기존 DB나 실행 중인 서버 없이 백업 폴더만으로 검사합니다.

외장 디스크를 사용하면 `photo-library-20261022` 폴더 전체를 새 장치에 연결하거나 복사하세요. SSH가 가능한 Linux/macOS 장치 간에는 다음처럼 전송할 수 있습니다. `user@new-host`는 실제 계정·호스트로 바꾸고 새 장치의 `/backup`은 미리 준비하세요. 같은 이름의 대상 백업 폴더가 없는 상태에서 실행합니다.

```bash
scp -rp /backup/photo-library-20261022 user@new-host:/backup/
```

`manifest.json`, `db/`, `managed/`를 모두 옮겨야 합니다. `managed/.trash` 등 숨김 파일·폴더도 포함하세요. **전송 후 새 장치에서 같은 `backup-check` 명령을 다시 실행**해 전송 누락·손상이 없는지 확인합니다. 외장 디스크에 직접 백업했다면 별도 네트워크 전송 없이 그 경로를 다음 단계의 `--backup`으로 지정하면 됩니다.

### 4. 새 장치에서 새 경로로 복원

새 장치에 저장소 코드와 [설치 및 실행](#설치-및-실행)의 Python 의존성을 준비한 뒤 실행합니다. `/data` 상위 디렉토리의 쓰기 권한과 복원 용량을 확보하고, `/data/restored-photos` 자체는 미리 생성하지 마세요. 복원 명령에는 이전 장치의 `--db`·`--root`가 필요하지 않습니다.

```bash
python3 apps/photo_browser/cli.py restore \
  --backup /backup/photo-library-20261022 --destination /data/restored-photos
```

성공하면 `status: "completed"`와 새 `db`, `managed_root`, `root`를 반환하고 `/data/restored-photos/restore.json`을 생성합니다. 복원 도중 파일별 무결성을 확인하며 DB의 관리 파일 참조도 새 경로로 갱신합니다. 실패한 경우 출력 오류를 해결하고 다른 새 경로에서 재시도하세요.

### 5. 복원된 설정 확인과 서버 실행

```bash
# 반환된 새 경로로 설정 확인
python3 apps/photo_browser/cli.py --db /data/restored-photos/db \
  --root /data/restored-photos config

# 복원 완료 후 서버 시작
python3 apps/photo_browser/app.py --root /data/restored-photos \
  --directory /data/restored-photos/managed --db /data/restored-photos/db
```

브라우저에서 <http://127.0.0.1:7081/>에 접속해 사진·동영상 열기, 이벤트·태그 검색, 휴지통 목록을 확인하세요. 기존 서버가 같은 장치의 7081 포트를 사용 중이면 종료하거나 새 서버에 `--port 7082`를 지정합니다. 비밀번호 인증을 사용했다면 실행 전에 `PHOTO_BROWSER_PASSWORD`도 별도로 설정하세요.

원본 소스를 옮기지 않아도 관리 복사본이 있는 사진은 열 수 있습니다. `compare`는 **현재 원본과의 대조**이므로 원본이 연결되지 않은 장치에서는 누락을 보고할 수 있습니다. 백업 파일 검증은 `backup-check`, 복원 완료 여부는 `restore` 결과와 실제 라이브러리 열기로 확인하세요. 원본까지 재연결한 뒤 필요하면 `compare`를 실행합니다.

### Windows PowerShell 예시

설치한 가상환경의 Python을 직접 사용합니다. 아래 `E:/photo_db`, `E:/`, `F:/backups`, `E:/restored-photos`는 실제 경로로 바꾸고, 백업·복원 대상 폴더는 존재하지 않아야 합니다. 장치 간 전송과 성공 결과 확인은 위 절차와 같습니다.

```powershell
.\apps\photo_browser\.venv\Scripts\python.exe apps/photo_browser/cli.py --db E:/photo_db --root E:/ backup --destination F:/backups/photo-library-20261022
.\apps\photo_browser\.venv\Scripts\python.exe apps/photo_browser/cli.py backup-check --backup F:/backups/photo-library-20261022
.\apps\photo_browser\.venv\Scripts\python.exe apps/photo_browser/cli.py restore --backup F:/backups/photo-library-20261022 --destination E:/restored-photos
.\apps\photo_browser\.venv\Scripts\python.exe apps/photo_browser/app.py --root E:/restored-photos --directory E:/restored-photos/managed --db E:/restored-photos/db
```

### 저장 구조와 보존 범위

백업 결과는 다음 구조입니다. `manifest.json`은 모든 복사가 성공한 뒤 기록하며 파일별 상대 경로·크기·수정 시각·SHA-256과 이전 DB·관리 루트를 포함합니다.

```text
photo-library-20261022/
  manifest.json
  db/          설정·카탈로그·체크포인트·보고서 등
  managed/     실제 관리 사진·동영상·휴지통 등

restored-photos/
  restore.json 복원 결과와 실행 경로 안내
  db/          새 경로로 갱신된 DB
  managed/     검증하여 복원한 관리 파일
```

백업은 파일을 복사하고 원본·사본의 SHA-256을 비교합니다. 등록된 사용 가능한 관리 복사본이 없거나 스캔 값과 다르면 실패하며, DB 전체 목록·수정 상태가 복사 중 바뀐 경우도 실패합니다. 아직 병합하지 않아 관리 복사본이 없는 활성 항목의 수는 `active_items_without_managed_copy`로 알립니다. **이 값이 0보다 크면 해당 항목의 메타데이터만 포함되며 원본 사진 바이트는 백업되지 않습니다.** 먼저 필요한 병합을 완료하고 백업하세요.

`backup-check`는 파일 목록·크기·SHA-256을 다시 확인합니다. `restore`도 각 파일을 검증한 뒤 새 DB와 관리 경로를 연결합니다. 카탈로그의 관리 `path`·`uri`, 휴지통의 이동 경로, 병합 체크포인트와 JSON 보고서의 DB·관리 경로를 갱신합니다. 사진 파일은 재인코딩하거나 EXIF를 쓰지 않습니다. 폴더 백업은 `copy2`로 파일 수정 시각을 보존하며 ZIP 복원은 manifest에 기록한 수정 시각을 적용합니다. 목적 파일시스템에 따라 시각 정밀도·권한 보존 범위는 달라질 수 있으며 생성 시각 보존은 보장하지 않습니다. 사용자 분류·촬영 정보는 유지합니다. 과거 HTML 보고서와 일반 텍스트 경로 히스토리는 당시 내용 그대로 보존하므로 이전 경로가 표시될 수 있습니다.

원본 소스 폴더와 원격 인증 환경변수, 앱 실행 코드·Python 환경은 백업 대상이 아닙니다. 새 장치에도 앱과 의존성을 설치하고 인증 값을 별도로 설정하세요. 원본 소스 경로·URI는 유지하며 관리 복사본만으로도 사진을 열 수 있습니다. 원본을 다시 스캔·병합하려면 원본 경로를 새 장치에 연결하고 필요하면 설정의 소스 경로와 서버 허용 루트를 조정하세요. 소스 설정을 바꾸면 이전 스캔 세션 이어하기 대신 새 스캔이 필요할 수 있습니다.

### 오류 처리와 재실행

| 증상 | 확인·처리 방법 |
| --- | --- |
| 대상 디렉토리가 이미 존재함 | 기존 데이터를 보존하고 다른 새 대상 경로를 지정합니다. 빈 폴더도 대상으로 사용할 수 없습니다. |
| 다른 작업이 실행 중임 | 웹의 스캔·병합·검증 등 작업이 끝난 후 재실행합니다. `.write.lock` 파일을 삭제해 해결하지 마세요. |
| 파일 목록·무결성 검사 실패 | 완성된 백업 폴더 전체를 옮겼는지 확인합니다. 원본 백업에서도 실패하면 기존 라이브러리에서 새 백업을 생성합니다. |
| 디스크 공간 부족 | 대상 디스크에 DB와 관리 파일을 함께 저장할 공간을 확보한 뒤 새 경로로 재실행합니다. |
| 심볼릭 링크 발견 | 링크로 연결한 외부 파일은 자동 수집하지 않습니다. 백업할 실제 DB·관리 파일 구성을 확인한 뒤 다시 실행합니다. |
| 강제 종료 후 미완성 폴더가 남음 | 이어하기는 지원하지 않으므로 다른 새 경로로 다시 실행합니다. 기존 완료 백업은 유지합니다. |

폴더 백업·복원 대상은 **존재하지 않는 새 디렉토리**, ZIP 백업 대상은 **존재하지 않는 새 파일**이어야 하며 기존 라이브러리를 덮어쓰지 않습니다. DB·관리 루트와 백업은 서로 포함되지 않는 별도 경로를 사용하고, 백업 폴더를 원본 스캔 경로 아래에 두지 마세요. 실패·일반 중단 시 이번에 생성한 출력 폴더만 정리합니다. 완료된 백업에는 `manifest.json`, 완료된 복원에는 `restore.json`이 있습니다. 정상은 종료 코드 0, 검증·복사 오류는 1, `Ctrl+C` 중단은 130입니다.

백업 시 기존 DB 작업 잠금을 획득하므로 웹서버의 다른 쓰기 작업과 충돌하면 거부합니다. 가장 안정적인 이전 절차는 기존 서버·외부 파일 변경을 중지한 후 백업하고 검증하는 것입니다. 새 경로 복원이므로 기존 서버는 계속 실행할 수 있지만 복원이 완료되기 전에는 복원 대상 서버를 시작하지 마세요. 백업 자체도 검사 중 수정하지 마세요. 성공한 백업과 기존 데이터는 복원 성공을 확인할 때까지 보관하세요.

## 설정 항목

### DB와 관리 디렉토리 위치 찾기

앱 시작 및 설정 저장 시 DB의 `config.json`과 DB·관리 폴더 양쪽의
`.photo-browser-location.json`을 하나의 저장 작업으로 갱신합니다. 관리 폴더가 없으면 생성합니다.
두 안내 파일은 동일한 `pair_id`와 `saved_at`을 가지며, `config.json`에도
`pair_id`와 `pair_saved_at`을 저장합니다. 기존 ID는 재시작·관리 경로 변경 시 유지하고,
ID 없는 기존 설정에는 자동으로 ID를 부여합니다. 변경이 없으면 파일을 다시 쓰지 않습니다.

서로 다른 ID의 DB와 관리 폴더는 연결을 거부합니다. ID 없는 기존 관리 폴더에 다른 DB의
경로가 기록되어 있어도 연결을 거부합니다. 같은 관리 폴더를 저장하는 프로세스끼리는 잠금으로 직렬화합니다.
DB가 다른 여러 라이브러리에는 각각 별도의 관리 폴더를 지정하세요.

각 안내 파일에는 `db`, `managed_root` 절대 경로와 파일 위치 기준의
`db_relative`, `managed_root_relative` 상대 경로가 들어 있습니다.
Windows에서 서로 다른 드라이브에 있으면 상대 경로는 `null`입니다.
예를 들어 `cat /data/photo_library/.photo-browser-location.json`으로 짝의 경로와 ID를 확인합니다.

여러 파일·디스크에 걸친 물리적 동시 쓰기는 불가능하므로 DB의
`.photo-browser-pair-pending.json`에 저장할 내용을 먼저 기록합니다. 일반 저장 오류는 이전
설정으로 되돌리고, 프로세스 중단으로 남은 작업은 다음 앱/CLI 시작 시 완료합니다.
완료 후 중단 복구 기록은 삭제합니다. ID와 경로 기록은 자동 사진 복구를 수행하지 않습니다.
백업 복원 시 원본과 분리된 새 짝 ID를 생성하고 두 경로를 함께 다시 기록합니다.

### 여러 소스와 DB·managed 연결 이력

여러 등록 소스(`sources[]`)는 하나의 DB·managed 쌍(`pair_id`)으로 연결됩니다.
연결 이력은 DB와 관리 폴더 각각의 `.photo-browser-pair-history/`에 이벤트별 JSON으로 저장합니다.
각 이벤트에는 고유 `event_id`, UTC `recorded_at`, 변경 사유(`reason`),
변경 전·후(`before`/`after`)의 `pair_id`, DB·managed 경로, 전체 소스 목록을 기록합니다.
소스 정보에는 ID·프로토콜·경로·분류·소유자·재귀 옵션만 포함하며 인증정보는 제외합니다.

최초 시작·기존 설정의 최초 이력 생성, 설정 변경, 소스 ID 변경·등록 해제,
백업 복원을 기록합니다. 변경 없는 재시작은 중복 기록하지 않습니다.
이력 파일도 설정 및 양쪽 위치 파일과 같은 저장 작업에 포함하므로, 이력 저장이 실패하면
설정 변경도 되돌립니다. 중단 복구 시 같은 이벤트 ID를 사용합니다.

조회 방법:

```sh
python cli.py --db /data/photo_db --root /data pair-history
```

웹 API는 `GET /api/pair-history`이며 기존 인증 정책을 따릅니다.
최근 100개를 최신순으로 반환하고 `total`에 전체 기록 수를 제공합니다.
손상된 이력은 덮어쓰지 않고 `errors`에 표시합니다. 원본 JSON은 삭제 없이 보관합니다.
DB 설정이 손상되어 서버를 시작할 수 없어도 양쪽의 이력 파일을 직접 읽어
과거 소스와 경로 연결을 확인할 수 있습니다. 이력은 자동 복구 명령을 실행하지 않습니다.
백업 복원 시 과거 이력은 당시 경로와 ID를 보존하고 새 쌍 생성 이벤트를 추가합니다.
기능 추가 이전의 변경 내역은 소급해서 복원할 수 없습니다.

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

### 디렉토리 경로 히스토리

Update 또는 기존 폴더 탐색의 스캔 시작으로 사진 조회가 성공하면, 서버의 **`db/history.txt`**에 경로와 날짜·시간(KST), 하위 폴더 포함 여부를 저장합니다. 실제 위치는 `--db`로 지정한 DB 아래입니다. UTF-8 JSON Lines 형식으로 한 줄에 방문 기록 하나를 저장하며 최근 **1,000개**를 유지합니다. 초과하면 가장 오래된 기록부터 제거합니다. 같은 경로라도 다시 Update한 방문은 별도 시각으로 기록하고, 다음 묶음 불러오기·필터 변경·실패한 조회는 추가하지 않습니다.

상단 **경로 히스토리**를 펼쳐 날짜·시간과 경로를 확인하고, 항목을 선택한 뒤 **선택 경로 적용**을 누르면 저장된 하위 폴더 옵션과 함께 다시 불러옵니다. 히스토리 조회 자체는 사진 스캔을 시작하지 않습니다. 서버 재시작이나 브라우저 새로고침 후에도 유지되며, 새 페이지의 기본 입력값은 기존처럼 `--directory`입니다. 히스토리는 같은 DB를 사용하는 접속자들이 공유합니다.

```json
{"id":"방문ID","recorded_at":"2026-10-22T15:30:00.123456+09:00","path":"/data/photos","recursive":true}
```

`GET /api/directory-history`로 최신순 기록을 조회하고 `POST /api/directory-history`에 `path`, `recursive`를 전달해 기록합니다. 변경 API의 인증·요청 헤더와 허용 루트 검사를 적용합니다. 현재 허용 루트 밖의 과거 기록은 화면 목록에서 제외합니다. 히스토리 저장 실패는 사진 표시를 막지 않고 별도 오류로 안내하며, 임시 파일 교체 방식으로 이전 정상 기록을 보존합니다. 손상된 JSON 행은 조회 시 건너뛰고 다음 저장 전 원본을 `history.corrupt.<ID>.txt`로 백업합니다. 이 백업은 1,000개 제한 대상이 아니므로 필요시 별도로 관리하세요.

상단 **현재 경로 설정 → 현재 탐색 디렉토리** 입력창에는 처음 접속할 때 `--directory`의 시작 경로가 표시됩니다. 경로 문자열을 수정하고 옆의 **Update**를 누르면 기존 폴더 탐색 탭으로 전환하여 해당 폴더의 사진·동영상을 즉시 불러옵니다. Enter로도 실행할 수 있으며 기존 날짜·형식 필터는 초기화하고, 하위 폴더 포함 옵션은 유지합니다. 기존 폴더 탐색에서 다른 경로를 불러온 경우에도 상단 입력창을 실제 조회된 경로로 동기화합니다.

허용 루트(`--root`) 밖이나 존재하지 않는 경로는 오류를 표시합니다. 이 입력창은 현재 페이지에서 표시할 폴더를 변경하며, 서버의 실행 인수·등록된 소스·관리 디렉토리는 변경하지 않습니다. 페이지를 새로 열면 서버의 시작 경로를 다시 사용합니다. 라이브러리 탭은 JSON에 등록된 미디어를 조회하므로 폴더 경로 변경 결과는 **기존 폴더 탐색** 갤러리에 표시합니다.

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

`test_workflow.py`는 설정·다중 소스 스캔·DB 발행·부분 병합·오류·재시작·캐시 무효화를 검사합니다. 단계 표시 스크립트의 완료·미확정 진행·조회 실패·복구 동작은 Node.js가 설치된 개발 환경에서 `node apps/photo_browser/test_workflow_ui.js`로 검사할 수 있습니다(저장소 루트 기준, 외부 패키지 불필요). Node.js는 서버 실행에는 필요하지 않습니다.

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

### 기존 사진의 소스 분류 적용과 병합 미리보기

소스 등록 폼의 카테고리·소유자는 신규 사진의 기본값입니다. 기존 사진까지 변경하려면 다음 순서를 사용하세요.

1. 소스의 `설정 불러오기`로 값을 불러온 뒤 카테고리·소유자를 수정하고 `등록 / 같은 ID 수정`으로 저장합니다.
2. 해당 소스의 **기존 사진에 카테고리·소유자 적용**을 누릅니다. 해당 소스에 연결된 기존 활성 사진의 두 분류 값을 교체합니다. 개별 수정한 분류도 교체하므로 확인창에서 적용 값을 확인하세요. 태그·이벤트·사람과 원본·관리 복사본 경로는 유지합니다.
3. **전체 병합 미리보기**를 누릅니다. 저장된 설정과 현재 DB 분류를 다시 읽어 새 미리보기를 생성합니다. 이전 미리보기 JSON은 과거 기록으로 남습니다.
4. 작업 결과 JSON의 `settings`에서 허용 루트·DB·관리 경로·소스 설정·출력 구조를, `operations`에서 사진별 입력 위치·카테고리·소유자·날짜·출력 경로를 확인합니다. `operations[].original_destination`은 원래 예정 경로, `destination`은 충돌을 해결한 실제 예정 경로입니다. 이름이 바뀌면 `renamed: true`, `rename_reason: "name_collision"`을 기록하며, `renamed_count`로 구분된 항목 수를 표시합니다. `destination_conflicts`는 자동 이름 구분 후에도 남은 충돌 목록입니다.
5. 경로와 경고를 확인한 뒤 **전체 병합 실행**을 누릅니다. 실행 시점의 설정과 분류로 다시 계산합니다.

미저장 폼 값은 적용되지 않습니다. 갱신은 실제 사진 복사·이동을 하지 않으며, 이미 생성된 `family` 등의 복사본도 자동 이동·삭제하지 않습니다. 분류 변경 후 새 경로로 병합하면 기존 복사본이 남을 수 있습니다. 경로 미리보기는 실제 파일의 해시·접근 권한·디스크 용량 전체를 검증하는 기능은 아닙니다.

### 사진 목록 조회를 생략하고 소스 설정 열기

`http://서버주소:7081/?panel=sources`로 접속하면 소스 설정 화면을 먼저 열며 초기 사진 목록과 필터 목록 조회를 생략합니다. 작업 완료 후에도 라이브러리 탭이 숨겨져 있으면 사진 목록을 자동 조회하지 않습니다. 소스 설정 저장과 확인을 위한 경로이며, Python 세그멘테이션 오류의 근본 해결을 의미하지는 않습니다. 미디어 라이브러리 탭을 선택하면 사진 조회를 실행합니다.

### 병합 실행 전 공간 검사

전체 병합 실행과 이어하기는 사진을 복사하기 전에 새 출력 파일의 총 바이트와 디스크 여유 공간을 검사합니다. 동일 내용으로 같은 출력 경로를 공유할 항목은 한 번만 계산합니다. 기존 파일의 SHA-256과 비교해 같은 내용이면 신규 용량에서 제외하고, 다른 내용이면 자동으로 구분한 새 경로의 파일 크기를 포함합니다. 미리보기도 동일한 이름 선택 규칙으로 경로를 표시하지만, 그 이후 디스크 상태가 바뀌면 실행 시 다시 이름을 선택합니다.

DB의 세대별 JSON·체크포인트·보고서 증가 예상량과 설정된 최소 여유 공간도 포함합니다. 출력과 DB가 같은 디스크면 합산하고, 다른 디스크면 각각 검사합니다. 원격 소스는 임시 다운로드에 필요한 공간도 검사합니다. 부족하면 **공간 부족 · 실행 안 함**으로 표시하고 경고창에 여유·필요 용량을 알립니다. 이 경우 새 사진 복사나 병합 DB 반영은 시작하지 않으며 작업 결과 기록만 남습니다. 결과의 `disk_space`에 계산 내역을 제공합니다. DB 증가량은 보수적인 추정이며 실행 중 다른 프로그램이 사용한 공간이나 실제 파일 크기 변경까지 예약·보장하지는 않습니다.

### 병합 실행 보고서

병합 진행 카드에는 **최초 병합 시작 시각(KST)**과 **시작 후 경과 시간**을 표시하며 실행 중에는 1초마다 갱신합니다. 새로고침·이어하기에도 최초 시작 시각을 유지하고 종료된 작업의 시간은 종료 시점에서 멈춥니다. 이어하기의 경과 시간에는 중지·대기 시간도 포함되며, 각 실행의 실제 소요 시간은 실행별 보고서의 `duration_seconds`로 확인합니다. 이전 버전 기록에 시작 시각이 없으면 같은 병합 ID의 작업 접수/시작 기록 중 가장 이른 시각을 사용합니다.

**전체 병합 실행**과 **병합 이어하기**는 실행할 때마다 `db/reports/merges` 아래에 JSON과 HTML 보고서를 함께 저장합니다. 실제 DB 경로를 `--db`로 지정했다면 그 디렉토리 아래에 생성됩니다. 소스·스캔·병합 화면의 **병합 보고서 기록**에서 과거 실행을 조회하고 **HTML 보고서 보기**, **JSON 다운로드**를 선택할 수 있습니다. 작업 내역의 해당 병합 카드에도 보고서 링크를 표시합니다. CLI 병합도 같은 보고서를 저장하며 반환 JSON의 `history_report.files`에 실제 저장 경로를 제공합니다.

| 내용 | 저장 필드와 해석 |
| --- | --- |
| 실행 시간 | `started_at`, `finished_at`, `duration_seconds`; 작업 실행 시작부터 전후 집계 완료까지. 대기열 대기 시간은 제외 |
| 입력과 출력 | `managed_root`, `db`, `source_settings`, `sources`; 소스 ID·원본 루트·프로토콜·호스트와 카테고리·소유자별 대상 수 |
| 이번 처리 수 | `summary.target_count`, `processed_count`, `copied_count`, `reused_count`, `error_count`, `skipped_count` |
| 동일 내용 중복 | `reused_count`는 기존 파일을 실제로 재사용한 항목 수. `identical_content_duplicate_count`는 이번 대상 안에서 같은 스캔 SHA-256이 반복된 항목 수이며 재사용 수와 별도 지표 |
| 이름 중복 처리 | `renamed_copied_count`, `renamed_files`; 내용이 달라 새 이름으로 실제 복사한 항목의 원본 위치·변경 전 경로·새 저장 경로·용량. 이미 구분된 이름의 파일을 재사용한 수는 `renamed_reused_count` |
| 병합 전 상태 | `before`: 파일·하위 디렉토리 수, 용량, 디렉토리별 직접/하위 포함 집계, 파일별 상대 경로·크기·수정 시각, 볼륨 여유 공간 |
| 병합 후 상태 | `after`: 동일한 방식의 집계 |
| 실제 변화 | `delta`: 추가·제거·크기/수정 시각 변경 파일 수와 목록, 전체 파일 수·용량 증감 |
| 파일별 실행 내역 | `operations`: 이번 실행에서 처리한 항목의 ID·원본·저장 경로·상태·오류 |

JSON의 시각은 시간대가 포함된 UTC ISO 형식이며 HTML에는 한국 표준시(KST)로 표시합니다. HTML 보고서는 외부 스크립트나 인터넷 연결 없이 열 수 있습니다.

중지한 실행과 이어한 실행은 **각각 다른 `report_id`**를 가지며 **같은 `merge_id`**로 연결됩니다. 각 보고서의 파일 수와 복사 수는 이번 실행 범위만 집계합니다. `summary.previous_processed_count`는 이전 실행까지 처리한 수이고 `session_target_count`는 병합 세션 전체 대상 수입니다. 병합 체크포인트의 `history_report_ids`에서도 연결된 보고서를 확인할 수 있습니다. 미리보기는 실제 실행 보고서를 만들지 않으며 기존 `plans` 기록만 저장합니다.

전후 상태는 파일 내용을 전부 다시 읽는 대신 경로·크기·수정 시각을 조사합니다. 용량은 **논리적 파일 크기 합계(bytes)**이며 실제 할당 블록·압축·중복 제거된 물리 용량과 다를 수 있습니다. 볼륨의 사용량·여유 공간은 별도로 저장합니다. 미디어 외 일반 파일도 집계하지만 `.trash` 디렉토리, 심볼릭 링크, 숨김 `.part` 임시 파일은 제외합니다. 빈 디렉토리도 구성에 포함합니다. 조회 권한 오류 등은 `errors`와 `complete: false`로 남기므로 불완전한 집계를 확정값으로 사용하지 마세요.

보고서용 집계 때문에 병합 전후에 관리 디렉토리를 각각 한 번씩 순회하며, 진행 카드에 **보고서용 관리 디렉토리 집계 중**으로 표시합니다. 다른 프로그램이 동시에 파일을 추가·삭제하면 전후 변화에도 반영됩니다. 따라서 `delta.added_count`(실제 디렉토리의 추가 경로 수)와 `summary.copied_count`(이번 작업의 성공 복사 수)를 구분해 확인하세요.

공간 부족으로 시작하지 못한 실행과 저장 후 중지한 실행도 해당 상태로 보고서를 남깁니다. 실행을 시작할 때 초기 보고서를 저장하고 종료 시 갱신하므로 프로세스가 비정상 종료되면 `running` 상태의 불완전한 보고서가 남을 수 있습니다. 보고서 저장 자체가 실패하면 실행 결과의 `history_report_error`와 경고를 확인하세요. 이전 버전의 병합 기록을 자동으로 보고서로 변환하거나 오래된 보고서를 자동 삭제하지는 않습니다. 보고서에도 전체 파일 목록이 저장되므로 DB 공간과 백업에 포함하세요.

보고서 API는 앱의 기존 인증을 따릅니다.

```text
GET /api/merge-reports?offset=0&limit=20         보고서 요약 목록(최대 100개/요청)
GET /api/merge-reports/<report_id>/html          HTML 보기
GET /api/merge-reports/<report_id>/json          JSON 보기
GET /api/merge-reports/<report_id>/json?download=1  JSON 다운로드
```

### 중복 소스 찾기

**중복 소스 찾기** 탭의 **중복 소스 검색**은 서로 다른 소스 ID의 스캔된 활성 미디어를 비교합니다. 상대 경로 목록·각 파일의 크기·파일 수·총 바이트가 모두 같으면 중복 후보로 표시하며, 마지막 스캔의 SHA-256까지 같은지도 별도로 표시합니다. 파일 내용이 다르면 같은 크기와 이름만으로 동일한 사진이라고 판단하지 마세요. 비어 있는 소스는 후보에서 제외합니다. 실제 디스크를 재검색하는 기능이 아니므로 각 소스를 최신 상태로 스캔한 뒤 사용하세요. 지원 미디어만 비교하며 일반 문서 등은 비교하지 않습니다.

그룹에서 유지할 소스를 선택하고 **소스 해제·관리 복사본 삭제**를 누르면 비교 조건을 다시 검사한 뒤 해당 소스 전용 관리 복사본을 영구 삭제하고 소스 등록을 해제합니다. 원본은 보존하며 다른 소스가 참조하는 공유 관리 파일은 삭제하지 않습니다. 전용 사진 항목은 DB에 보존하되 라이브러리·병합 대상에서 제외합니다. 소스를 다시 등록하고 스캔하면 원본에서 복사할 수 있습니다. 삭제 내역과 변경 전 항목은 `db/source_cleanup`에 기록하며 일부 삭제가 실패하면 소스 등록을 유지하고 오류를 표시합니다. 대량 정리는 백그라운드 작업으로 실행합니다. 실행 중인 작업이 있거나 비교 결과가 바뀌었으면 등록 해제를 거부합니다. 파일 목록은 100개씩 펼쳐 확인할 수 있습니다.


## 향후 구현 방향: 지능형 사진 갤러리

다음은 **아직 구현하지 않은 설계**입니다. [intelligent_photo_gallery_design.md](intelligent_photo_gallery_design.md)에 데이터 포맷·API·화면·저장 및 검색 연결을 정리했습니다. 기존 [spec.md의 메타데이터 관리 제안](spec.md#10-향후-제안-메타데이터-관리-기능)을 다음 순서로 구체화합니다.

1. **태그 데이터 포맷 정의:** 이벤트·사람·장소·일반 태그 사전과 ID, 사진별 연결, 사용자 설명, 출처·revision·변경 이력을 정의합니다.
2. **태그 입력·수정·삭제·관리:** 기존 라이브러리에 개별/일괄 추가·교체·제거, 사전 관리, 변경 이력·취소와 검색을 제공합니다. 사진 원본·촬영 정보·파일 수정 시각은 유지합니다.
3. **Gemma 4 31B 설명 생성과 검색:** 사용자 annotation·추출한 EXIF와 원본 이미지 바이트(또는 동일 SHA-256의 관리 복사본)를 `gemma4:31b`에 전송합니다. 도슨트 시스템 프롬프트로 한 줄 제목·2~3문장의 해요체 설명·추천 태그를 JSON으로 받고, 사용자 입력과 분리해 사진 ID·파일 해시·입력 문맥·모델 버전과 함께 저장합니다. 확인되지 않은 장소·역사 정보는 단정하지 않으며 키워드 검색에서 의미 검색으로 확장합니다. 실제 전송과 구현은 별도 개발 단계에서 진행합니다.


## 작업 화면의 파일 경로와 처리 단계

작업 진행 카드에는 경로의 역할과 처리 동작을 함께 표시합니다. 화면은 폴링으로 갱신되므로 **현재 또는 가장 최근 보고된 처리 정보**이며 모든 파일의 순간적인 단계를 보여주는 것은 아닙니다. 완료·중단된 작업에는 마지막 처리 정보를 표시합니다.

| 표시 역할/동작 | 경로의 의미 |
| --- | --- |
| 원본 소스 파일 · 스캔 분석 | 로컬 원본 경로 또는 원격 URI. 메타데이터·해시·변경 여부를 조사하며 병합 복사가 아님 |
| 내용 비교 대상 · 기존 관리 파일 | 관리 디렉토리에 이미 존재하는 파일. 스캔 SHA-256과 비교해 재사용 또는 중복 이름을 결정하며 캐시된 해시를 사용할 수 있음 |
| 복사 대상 · 여유 공간 계산 | 신규 복사량을 계산하는 관리 저장 예정 경로. 아직 복사 중이라는 뜻이 아님 |
| 원본 소스 파일 · 읽기 | 복사할 원본을 읽거나 원격 파일을 임시 수신 중 |
| 복사 대상 · 복사 중 | 표시 경로는 최종 관리 위치이며 실제 바이트는 검증용 임시 파일에 복사 중 |
| 복사 검증 대상 · 임시 파일 | `.part` 임시 복사본의 SHA-256을 확인 중. 최종 관리 경로를 별도 표시 |
| 복사 대상 · 최종 저장 | 검증된 복사본을 관리 경로에 게시 중 |
| 복사 완료 / 기존 파일 재사용 | 해당 대상의 처리 결과. 지금 복사하고 있다는 뜻이 아님. 재사용은 새 복사를 하지 않음 |
| 병합 미리보기 저장 예정 경로 | 실행 시 저장할 관리 대상이며 실제 복사는 하지 않음 |
| 보고서 집계 대상 · 관리 디렉토리 | 병합 전후 보고서용 파일 수·용량 집계. 사진 파일 하나의 복사 상태가 아님 |
| ZIP에 담는 미디어 이름 | 다운로드 ZIP에 넣는 항목의 원래 이름이며 서버의 전체 파일 경로가 아님 |

병합 중에는 원본 소스와 최종 관리 경로를 함께 표시합니다. 경로의 역할과 동작은 진행 JSON의 `current_file_role`, `current_action`에 저장하며 `source_file`, `target_file`로 두 위치를 구분합니다. 체크포인트에도 마지막 처리 대상을 남깁니다. 기존 `current_file` 필드는 호환성을 위해 유지합니다.

이전 버전으로 시작한 병합 기록에는 역할·동작 필드가 없습니다. 이 경우 **최근 보고된 관리 대상 경로**로 표시하고, 당시 비교·복사·완료 중 어느 단계인지는 알 수 없다고 안내합니다. 실행 중인 서버는 새 코드로 자동 변경되지 않으므로 스캔·병합을 중지하고 저장한 뒤 서버 재시작 및 이어하기를 통해 새 표시를 적용하세요.
