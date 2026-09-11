# Nextcloud File Sync System

## 개요
이 디렉토리는 Nextcloud 파일 동기화 시스템과 관련된 다양한 응용 소프트웨어를 포함합니다. 
Nextcloud는 자체 호스팅 파일 동기화 및 공유 솔루션으로, 여러 클라이언트 도구, 서버 설정, 관리 스크립트, 플러그인 등을 제공합니다.

## Nextcloud 파일 디렉토리 위치 이동

이 저장소의 Docker 구성은 호스트 디렉토리를 컨테이너의 `/var/www/html`에 연결합니다. 따라서 호스트 경로만 변경하고, Nextcloud 내부 경로인 `/var/www/html/data`는 유지하는 것이 안전합니다.

### 1. 사전 확인 및 백업

`compose_script` 디렉토리에서 작업한다고 가정합니다. 사용하는 Compose 프로젝트가 다르면 해당 프로젝트 디렉토리와 서비스 이름을 바꾸세요.

```bash
cd apps/nextcloud/compose_script
docker compose ps
docker compose exec -u www-data app php occ config:system:get datadirectory
docker compose exec -u www-data app php occ maintenance:mode --on
docker compose exec db mariadb-dump -u root -p nextcloud > nextcloud_before_move.sql
```

DB 비밀번호 입력이 필요한 경우 `db.env`의 설정을 사용합니다. 데이터 디렉토리의 현재 호스트 경로와 디스크 여유 공간도 확인합니다.

```bash
grep '^VOL_PATH=' .env
df -h
du -sh "$(grep '^VOL_PATH=' .env | cut -d= -f2)/nextcloud_volume/data"
```

### 2. 권장 방법: 전체 Nextcloud 볼륨 이동

현재 [docker-compose.yml](compose_script/docker-compose.yml)는 `${VOL_PATH}/nextcloud_volume` 전체를 `/var/www/html`에 연결합니다. 이 경우 전체 디렉토리를 옮기면 `config/config.php`, 앱, 데이터의 경로가 함께 보존됩니다.

```bash
OLD_VOL_PATH=/home/tinyos/devel/nextcloud/vol
NEW_VOL_PATH=/mnt/nextcloud/vol

docker compose down
sudo mkdir -p "$NEW_VOL_PATH"
sudo rsync -aHAX --info=progress2 \
   "$OLD_VOL_PATH/nextcloud_volume/" \
   "$NEW_VOL_PATH/nextcloud_volume/"
sudo rsync -aHAX \
   "$OLD_VOL_PATH/mariadb_volume/" \
   "$NEW_VOL_PATH/mariadb_volume/"
sudo rsync -aHAX \
   "$OLD_VOL_PATH/nginx_proxy/" \
   "$NEW_VOL_PATH/nginx_proxy/"
```

복사 후 `compose_script/.env`의 `VOL_PATH`를 새 경로로 변경합니다.

```dotenv
VOL_PATH=/mnt/nextcloud/vol
```

이후 컨테이너를 시작하고 상태를 확인합니다.

```bash
docker compose up -d
docker compose ps
docker compose exec -u www-data app php occ config:system:get datadirectory
docker compose exec -u www-data app php occ maintenance:mode --off
```

`datadirectory` 출력은 계속 `/var/www/html/data`여야 합니다. 호스트 경로를 `config.php`에 직접 넣지 마세요.

### 3. 데이터 디렉토리만 별도 디스크로 이동

설정과 앱은 기존 `${VOL_PATH}/nextcloud_volume`에 두고 사용자 파일만 분리하려면 `docker-compose.yml`의 `app.volumes`에 데이터 마운트를 추가합니다.

```yaml
      volumes:
         - ${VOL_PATH}/nextcloud_volume:/var/www/html
         - ${NEXTCLOUD_DATA_PATH}:/var/www/html/data
```

`.env`에는 새 호스트 경로를 지정합니다.

```dotenv
NEXTCLOUD_DATA_PATH=/mnt/nextcloud/data
```

기존 데이터는 유지보수 모드와 컨테이너 중지 상태에서 복사합니다.

```bash
OLD_VOL_PATH=/home/tinyos/devel/nextcloud/vol

docker compose down
sudo mkdir -p /mnt/nextcloud/data
sudo rsync -aHAX --info=progress2 \
   "$OLD_VOL_PATH/nextcloud_volume/data/" \
   /mnt/nextcloud/data/
sudo chown -R 33:33 /mnt/nextcloud/data
docker compose up -d
docker compose exec -u www-data app php occ files:scan --all
docker compose exec -u www-data app php occ maintenance:mode --off
```

`33:33`은 Debian/Ubuntu 계열 이미지의 `www-data` UID/GID입니다. 다른 이미지에서는 다음 명령으로 실제 값을 확인한 뒤 사용합니다.

```bash
docker compose exec app id www-data
```

### 4. 이동 후 검증 및 정리

웹 로그인, 기존 파일 열기, 파일 업로드/다운로드, 공유 링크를 확인합니다. 문제가 있으면 즉시 유지보수 모드를 켜고 컨테이너를 중지한 뒤 원래 경로로 되돌립니다.

```bash
docker compose exec -u www-data app php occ maintenance:mode --on
docker compose logs --tail=100 app
docker compose exec -u www-data app php occ status
```

정상 동작을 확인하기 전에는 기존 호스트 디렉토리를 삭제하지 마세요. `http_yml`, `simple_http`, `multi_nc` 구성을 사용하는 경우에도 같은 원칙으로 해당 compose 파일의 `/var/www/html` 호스트 경로만 변경하면 됩니다.

## 실제 수행 사례: x86_64에서 ARM64 서버로 이전

작업 기록 기준 **2026-09-11 수행, 2026-09-12 문서화**한 사례입니다.
아래는 실제 수행 경과이며, 그대로 실행하는 자동화 절차가 아닙니다.
서비스 상태와 검증 결과도 작업 완료 시점 기준입니다.

### 이전 환경과 범위

| 항목 | 원본 | 대상 |
|---|---|---|
| 서버 주소 | `10.0.0.134` | `10.0.0.23` |
| CPU 아키텍처 | x86_64 | ARM64 |
| 운영체제 | Ubuntu 20.04 | Ubuntu 25.04 |
| HTML 호스트 경로 | `/mnt/lvm_7t/nextcloud_22080/html` | `/mnt/data/run/nextcloud_http/html` |
| DB 이전 방식 | 중지 상태의 물리 백업에서 SQL 추출 | 빈 MariaDB에 SQL 복원 |
| Nextcloud / MariaDB | 27.0.1 / 11.0.2 | 같은 버전의 ARM64 이미지 |

HTML 전체에는 사용자 데이터, 앱, `config/config.php`가 포함됩니다.
컨테이너 내부 경로는 `/var/www/html`, 데이터 경로는 `/var/www/html/data`로
유지했습니다. DB 원본 백업, 추가 DB 마운트 백업, 실제 운영 Compose 파일과
이미지 메타데이터도 별도로 보관했습니다. 원본 파일은 삭제하지 않았습니다.

### 실제 수행 순서

1. 원본 컨테이너의 실제 마운트와 버전을 확인하고 유지보수 모드를 켰습니다.
   Nextcloud를 중지한 뒤 SQL 덤프를 시도했으나, `oc_filecache`와
   `oc_activity`에서 인덱스 오류가 발생했습니다. DB도 정상 종료하여
   약 622MiB의 물리 백업을 확보했습니다. 실패한 부분 SQL은 완전한 백업으로
   취급하지 않았습니다.
2. HTML부터 전송하던 아카이브 스트림이 중단되어 원격에 약 188GiB의
   미완성 `.transfer/service.tar`가 남았습니다. 원본에서는 커널 오류로
   sudo와 Docker가 응답하지 않았으며, 원격 주소도 기존 `10.0.0.11`에서
   `10.0.0.23`으로 바뀌었습니다. 사용자 확인을 받은 SSH 호스트 키로
   대상 서버의 동일성을 확인했습니다.
3. 사용자가 원본 서버를 재부팅했습니다. 재접속 후 sudo와 Docker 응답,
   해당 부팅의 커널 로그를 확인했습니다. 원본 Nextcloud와 DB는 중지 상태로
   유지하고, 이미 풀린 원격 HTML에 누락 파일을 이어서 복사했습니다.
4. HTML 전송에는 `rsync -aHAX --numeric-ids`를 사용했습니다.
   일반 사용자 SSH 로그인과 sudo를 사용했고, 권한 보존을 위해 원격 루프백에만
   바인딩한 임시 인증 rsync 서버를 SSH 터널로 연결했습니다.
   `--remove-source-files`나 실제 삭제 옵션은 사용하지 않았습니다.
   최종 `rsync -aHAXn --numeric-ids --itemize-changes` 비교는 종료 코드 0,
   변경 항목 없음으로 완료했습니다. 요청에 따라 전체 HTML `--checksum`
   검사는 생략했습니다.
5. DB 물리 백업을 원본과 다른 임시 디렉터리에 풀고, 네트워크를 차단한
   MariaDB 11.0.2 임시 컨테이너에서 SQL을 다시 추출했습니다.
   원본 DB에 복구 명령을 실행하지 않았으며, 이번 SQL 추출은 성공했습니다.
   140개 테이블이 `mariadb-check`를 통과했고, 별도의 빈 임시 DB에 복원한 뒤
   모든 테이블의 행 수가 일치하는 것을 확인했습니다.
6. 완전한 SQL 약 120MiB와 DB 백업을 대상에 복사했습니다.
   DB 백업 두 파일과 SQL은 원본·대상의 SHA-256 일치를 확인했습니다.
   검증용 임시 컨테이너는 정리하고 원본 DB 백업은 보존했습니다.
7. 대상에 Docker 28.2.2와 Compose 2.37.1을 설치했습니다.
   x86_64 이미지를 그대로 옮겨 실행하지 않고, Nextcloud 27.0.1 및
   MariaDB 11.0.2의 ARM64 이미지를 다이제스트로 고정하여 사용했습니다.
8. 대상의 최초 SQL 자동 복원은 파일 읽기 권한 부족으로 중단됐습니다.
   최상위 서비스 폴더 접근 제한을 유지하면서 SQL 권한을 `600`에서 `644`로
   조정하고, 비어 있는 대상 DB에 직접 복원했습니다.
   Nextcloud 기동 전에 ARM64 DB에서도 원본의 140개 테이블 행 수와 일치함을
   확인하고 `metadata/DB_IMPORT_VERIFIED`로 기록했습니다.
9. Nextcloud를 시작하고 `trusted_domains`, `overwritehost`,
   `overwriteprotocol`, `overwrite.cli.url`을 새 주소에 맞게 설정했습니다.
   이전 프록시 관련 설정을 정리하고 데이터 지문 갱신 및 유지보수 모드 해제를
   수행했습니다. 외부 호스트에서 상태 API와 로그인 페이지를 확인했습니다.
10. 임시 rsync 서버, SSH 터널, 전송용 인증 정보를 정리했습니다.
    원본 서비스는 다시 시작하지 않았으며, 원본 파일과 백업을 보존했습니다.

### 완료 시점의 검증 결과와 제한

- HTML 논리 크기: `242,134,315,331`바이트, 약 225.5GiB.
- 일반 파일 108,344개, 디렉터리 26,791개. 재개 작업에서 일반 파일
  75,663개를 추가·갱신했으며 삭제한 파일은 없습니다.
- HTML 최종 비교는 크기·수정 시각·메타데이터 기준입니다.
  전체 파일 내용의 해시 일치를 검증한 것은 아니며, 이 비교만으로 대상에만
  존재하는 여분 파일이 전혀 없음을 보장하지도 않습니다.
- DB는 x86_64 임시 복원 시험과 ARM64 실제 복원 모두에서 140개 테이블의
  행 수가 원본 스냅샷과 일치했습니다. 행 수 비교는 모든 값의 의미적 무결성을
  보장하는 검사는 아닙니다.
- 대상 컨테이너 `nextcloud_http`, `nextcloud_db_http`가 실행됐고,
  Nextcloud는 `installed=true`, `maintenance=false`,
  `needsDbUpgrade=false`, 버전 `27.0.1.2`를 반환했습니다.
- `http://10.0.0.23:22080/login`에서 HTTP 200을 확인했습니다.
  사용자 로그인, 실제 파일 업로드·다운로드, 공유 링크 및 앱 기능은 별도
  사용자 확인 대상으로 남겼습니다.
- 이전 커널 오류의 근본 원인은 확정하지 않았습니다. 재부팅 후 복사와 SQL
  추출 성공만으로 원본 장치나 모든 데이터의 무결성을 단정하지 않습니다.
- `.transfer/service.tar`는 미완성 이력 파일입니다. 완전한 복원 묶음으로
  사용하면 안 됩니다. `TRANSFER_COMPLETE`는 파일 이전 완료 표시이며,
  모든 애플리케이션 기능 검증 완료를 뜻하지 않습니다.

### clone.py와 동일한 작업인가?

**목적은 같지만 동일한 절차는 아닙니다.** 이번 이전은 별도 명령과
`start-target.sh`를 사용했으며, 저장소의
[clone_proc/clone.py](http_yml/clone_proc/clone.py)를 그대로 실행한 사례가 아닙니다.

| 항목 | 이번 실제 작업 | `clone.py` |
|---|---|---|
| CPU | x86_64 → ARM64 | 동일 CPU 아키텍처만 허용 |
| Docker 이미지 | 동일 버전의 ARM64 이미지 다운로드 | 원본 이미지 저장·로드, 이미지 ID 확인 |
| DB | SQL 추출 후 빈 DB에 복원 | 중지된 DB의 물리 파일 복사 |
| DB 검증 | 테이블 검사, SQL 복원 시험, 140개 테이블 행 수 비교 | DB 접속과 Nextcloud 상태 확인 |
| SSH 전송 | 일반 사용자 로그인, sudo, 임시 rsync 서버와 터널 | root SSH 키 인증 |
| 중단 후 재개 | 기존 부분 복사본을 보완 | 기존 대상 디렉터리 거부 |
| 원본 서비스 | 이전 후에도 중지 유지 | export 종료 처리에서 원본 재시작 시도 |
| Docker 설치 | 원격에 설치 | 사전 설치 필요 |
| 파일 검증 | HTML 체크섬 생략, 메타데이터 비교 | 기본 메타데이터 비교, `--verify-content`로 체크섬 추가 가능 |
| 완료 묶음 | 별도 백업·SQL·완료 표시 사용 | `manifest.json`, `images.tar`, `data/`, `READY` 형식 |

공통점은 원본을 삭제하지 않는 복사, 소유권·권한 보존, 대상 주소 설정,
유지보수 해제 및 상태 확인입니다. 다만 이번 이전 디렉터리는 `clone.py`의
복원 묶음 형식이 아니며, 현재 실행 중인 대상에 `restore`를 다시 실행하는
용도로 사용할 수 없습니다.

동일 CPU 아키텍처 제한 문구를 추가한 것만으로 이번 작업 전체가 자동화된
것은 아닙니다. 같은 절차를 자동화하려면 ARM64 이미지 선택, SQL 이전·검증,
중단 후 재개, 원본 중지 유지 등을 별도로 구현해야 합니다.

### 기록 보관과 보안

대상 `/mnt/data/run/nextcloud_http/readme.md`와 `metadata/`에 상세 기록을
보관했습니다. 실제 Compose 파일, DB·SQL, HTML에는 비밀번호, Nextcloud
비밀 키와 사용자 데이터가 포함되므로 Git에 추가하지 않습니다.
이 문서에는 작업 경로와 내부 IP만 기록하고 인증 정보는 포함하지 않았습니다.
서비스를 공개 인터넷에 노출하기 전에는 HTTPS 및 접근 정책을 별도로 구성해야
하며, 원본과 대상에 동기화 클라이언트가 동시에 쓰지 않도록 관리해야 합니다.

## clipboardnextcloud.py 실행
-  python3 -m streamlit run clipboardnextcloud.py --server.headless true


## 내부 응용 소프트웨어 구성

### 1. 클라이언트 도구 (client/)
WebDAV 프로토콜을 사용하는 Nextcloud 클라이언트 애플리케이션입니다.

#### get_list.py
- **기능**: Nextcloud 서버에서 파일 목록을 가져오고 다운로드하는 Python 스크립트
- **주요 특징**:
  - WebDAV 프로토콜을 이용한 파일 접근
  - 재귀적 디렉토리 스캔 (서브디렉토리 포함)
  - JPG/JPEG 파일 자동 필터링
  - 파일 메타데이터 수집 (수정 날짜, 파일 크기)
  - 중복 다운로드 방지 (로컬 파일과 원격 파일 비교)
  - OCR 처리를 위한 이미지 다운로드 지원
- **의존성**: requests, Pillow, pytesseract, webdavclient3
- **설정**: config.json 파일을 통한 서버 정보 및 인증 설정

### 2. 서버 간 동기화 도구

#### txtoserver.py
- **기능**: 여러 Nextcloud 서버 간 파일 증분 복사 및 동기화
- **주요 특징**:
  - 소스 서버(A)에서 목적지 서버(B)로 파일 전송
  - WebDAV 프로토콜 사용
  - 중복 파일 방지 (ETag, 파일 크기, 수정 날짜 비교)
  - 증분 복사 지원 (변경된 파일만 전송)
  - 디렉토리 구조 자동 생성
  - SSL 인증서 검증 옵션
  - 연결 테스트 모드 (`--conn_test`)
  - PROPFIND 요청을 통한 서버 상태 확인
- **설정**: input.conf 파일 (INI 형식)
- **사용 예**:
  - `python3 txtoserver.py`
  - `python3 txtoserver.py /path/to/input.conf`
  - `python3 txtoserver.py --conn_test`

#### clipboardnextcloud.py
- **기능**: macOS 클립보드의 텍스트, HTML, 파일 URL, 이미지를 Streamlit 화면에 표시하고 Nextcloud에 Markdown 파일로 업로드
- **주요 특징**:
  - 현재 클립보드 내용 미리보기
  - 이미지 클립보드를 PNG base64 형태로 Markdown에 포함
  - 대상 Nextcloud 루트 아래에 날짜 디렉토리 `YYYY-MMDD`(예: `2026-0427`)를 만든 뒤 그 안에 업로드
  - 클립보드 전송 시 `YYYYMMDD_HHMMSS_devicename_clipboard.md` 파일 생성
  - `input.conf` 의 `[target]` 또는 `[destination]` 섹션 사용
  - 필요한 패키지(`streamlit`, `webdavclient3`)가 없으면 실행 중 자동 설치 시도
  - Telegram bot 메시지를 트리거로 사용하여 클립보드 전송 자동 실행 가능
  - 여러 PC에 같은 앱이 떠 있어도 같은 Telegram 트리거는 Nextcloud 공용 claim 경로를 사용해 한 번만 처리
- **실행 방법**:
  - `python3 -m streamlit run apps/nextcloud/clipboardnextcloud.py`
  - 설정 파일을 기본값이 아닌 경로로 쓰려면 앱 실행 후 사이드바의 `Config path` 에서 변경
- **macOS 앱 생성**:
  - `chmod +x apps/nextcloud/create_clipboardnextcloud_app.sh`
  - 플랫폼 자동 감지(`--platform auto`, 기본값)로 macOS는 `.app`, Windows는 런처 폴더를 생성
  - 기본적으로 `/Users/tinyos/devel_opment/venv/bin/python` 이 존재하면 그 Python을 사용
  - `apps/nextcloud/create_clipboardnextcloud_app.sh --python /path/to/venv/bin/python`
  - Windows 런처를 강제로 생성하려면 `apps/nextcloud/create_clipboardnextcloud_app.sh --platform windows --python /path/to/python.exe`
  - 기본 출력 경로는 `$HOME/Applications/ClipboardNextcloud.app`
  - Windows 기본 출력 경로는 `apps/nextcloud/ClipboardNextcloud/` 이며 `ClipboardNextcloud.bat` 실행
  - 다른 위치에 만들려면 `apps/nextcloud/create_clipboardnextcloud_app.sh --python /path/to/venv/bin/python "/원하는/경로/ClipboardNextcloud.app"`
  - Windows에서도 다른 위치를 쓰려면 마지막 인자로 출력 폴더 경로를 전달
  - 생성된 앱은 전용 포트 `localhost:8517` 기준으로 Streamlit을 실행하고, 필요 시 `127.0.0.1:8517`로도 접속을 시도
  - `--python` 을 생략하면 생성 시점의 `python3` 경로를 그대로 저장하므로, 개발용 virtual environment를 쓰려면 해당 venv의 Python 경로를 명시하는 것이 안전
- **설정 파일**:
  - 기본 경로: `apps/nextcloud/input.conf`
  - 예시 섹션: `[target]`, `[destination]`, `[settings]`, `[telegram]`

##### Telegram bot 연결 방법
`clipboardnextcloud.py` 는 Telegram bot 으로 들어온 특정 메시지를 감지하면 현재 PC의 클립보드를 즉시 Nextcloud 로 업로드할 수 있습니다.

1. Telegram bot 생성
   - Telegram 에서 `@BotFather` 를 열고 `/newbot` 실행
   - bot 이름과 username 을 입력
   - 발급된 `bot token` 을 복사

2. bot 과 대화 시작
   - 방금 만든 bot 과 1:1 대화창을 열고 `Start` 를 누르거나 아무 메시지나 1회 전송
   - 그룹에서 쓰고 싶다면 bot 을 그룹에 초대한 뒤, 그 그룹에 메시지를 1회 전송

3. `chat_id` 확인
   - 브라우저에서 아래 URL 호출
   ```text
   https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
   ```
   - 응답 JSON 에서:
     - 1:1 대화는 `message.chat.id`
     - 그룹은 음수 형태의 `message.chat.id`
   - 이 값을 `allowed_chat_id` 에 넣음

4. `input.conf` 에 Telegram 섹션 추가
   - 예시:
   ```ini
   [target]
   webdav_hostname = https://nextcloud.example.com
   webdav_root = /remote.php/dav/files/username/
   port = 443
   username = your_id
   password = your_password
   root = clipboard

   [destination]
   webdav_hostname = https://nextcloud.example.com
   webdav_root = /remote.php/dav/files/username/
   port = 443
   username = your_id
   password = your_password
   root = clipboard

   [settings]
   verify_ssl = true

   [telegram]
   enabled = true
   bot_token = 123456789:ABCDEF_your_bot_token
   allowed_chat_id = 123456789
   trigger_text = /clipboard
   poll_interval_seconds = 5
   reply_on_success = true
   ```

5. 항목 설명
   - `enabled`: Telegram 트리거 사용 여부
   - `bot_token`: `@BotFather` 가 발급한 토큰
   - `allowed_chat_id`: 허용할 단일 chat id
   - `trigger_text`: 이 문자열과 정확히 일치하는 메시지가 들어오면 전송 실행
   - `poll_interval_seconds`: Telegram polling 주기. 기본 5초
   - `reply_on_success`: 업로드 성공 시 bot 이 결과 메시지를 다시 보낼지 여부

6. 앱 실행
   ```bash
   python3 -m streamlit run apps/nextcloud/clipboardnextcloud.py --server.headless true
   ```
   - 앱이 실행 중일 때만 Telegram polling 이 동작
   - `클립보드` 탭의 업로드 영역에서 Telegram 상태 버튼 색이 바뀌며 트리거를 확인 가능

7. 동작 방식
   - Telegram 에서 `trigger_text` 와 동일한 메시지를 bot 으로 전송
   - 앱이 메시지를 감지하면 현재 PC 클립보드를 읽고 Nextcloud 로 업로드
   - 성공 시 Nextcloud 경로와 URL 을 bot 으로 회신 가능

8. 여러 컴퓨터에서 동시 사용 시
   - 여러 PC 에 같은 `bot_token` 과 `allowed_chat_id` 를 설정해도 같은 Telegram 메시지는 한 번만 처리되도록 구현됨
   - 내부적으로 Nextcloud 의 `root/.telegram_trigger_claims/<chat_id>/<update_id>` 경로를 사용해 먼저 잡은 인스턴스만 업로드 수행
   - 단, 어떤 PC 가 먼저 처리할지는 각 인스턴스의 polling 타이밍에 따라 달라짐
   - 특정 PC 만 반응하게 하려면 `trigger_text` 를 기기별로 다르게 두는 방식이 가장 단순함

9. 주의사항
   - Telegram 트리거는 현재 앱이 떠 있는 PC 의 클립보드를 업로드함
   - 앱을 처음 띄운 직전의 오래된 Telegram 메시지는 재실행하지 않도록 offset 상태를 `apps/nextcloud/resource/telegram_state.json` 에 저장
   - macOS 에서 클립보드 이미지/파일 URL 감지는 시스템 권한 상태에 영향을 받을 수 있음

### 3. Docker 구성 (compose_script/)
Docker Compose를 이용한 Nextcloud 서버 설치 및 설정

#### 구성 요소
- **docker-compose.yml**: 전체 스택 구성 정의
  - MariaDB 데이터베이스 서비스
  - Nextcloud Apache 애플리케이션 서버
  - Nginx 리버스 프록시
  - Let's Encrypt SSL 인증서 자동 관리
- **config.php**: Nextcloud 서버 설정 파일
- **.env**: 환경 변수 설정 (볼륨 경로 등)
- **db.env**: 데이터베이스 환경 변수
- **proxy/**: Nginx 프록시 설정
  - Dockerfile: 프록시 컨테이너 빌드 설정
  - uploadsize.conf: 업로드 파일 크기 제한 설정

#### 주요 설정 항목
- VIRTUAL_HOST: Nextcloud 도메인 URL
- LETSENCRYPT_HOST: SSL 인증서 발급 도메인
- LETSENCRYPT_EMAIL: Let's Encrypt 알림 이메일
- VOL_PATH: 데이터 볼륨 저장 경로

### 4. 서버 관리 도구 (management/)
Nextcloud 서버 관리 관련 명령어 모음

#### 주요 기능
- **Brute Force 공격 방어**: IP 주소 기반 차단 해제
  - `sudo docker logs -n 30 {컨테이너명}`: IP 주소 확인
  - `sudo docker exec -it -u 33 {컨테이너명} php occ security:bruteforce:reset {IP주소}`

### 5. 플러그인 (plugin/)

#### retention/
파일 보존 및 자동 태깅 플러그인

- **files_retention**: 파일 보존 정책 관리
  - 자동 파일 삭제 규칙 설정
  - 보존 기간 정책 적용
- **files_automatedtagging**: 파일 자동 태깅
  - 파일 유형별 자동 태그 할당
  - 워크플로우 자동화 지원

### 6. 다중 인스턴스 관리 (multi_nc/)
여러 Nextcloud 인스턴스 동시 운영

#### 특징
- 여러 Nextcloud 서버를 Docker Compose로 동시 운영
- 각 인스턴스별 독립적인 컨테이너 이름 설정
- 시스템 포트 분리 관리 (예: 9322 포트 사용)
- docker-compose-9322.yml: 포트 9322를 사용하는 추가 인스턴스 예시

### 7. 간단한 HTTP 서버 (simple_http/)
IOTstack 기반 Nextcloud 설치

#### 특징
- IOTstack 프레임워크 활용
- 간편한 설치 및 설정
- CURL 스크립트를 통한 원클릭 설치:
  ```bash
  curl -fsSL https://raw.githubusercontent.com/SensorsIot/IOTstack/master/install.sh | bash
  ```

### 8. 유틸리티 및 문서

#### direct_cp.md
- curl을 이용한 직접 파일 복사 방법
- .netrc 파일을 통한 인증 설정
- WebDAV 프로토콜로 백업 파일 전송

#### file_lock_issue.md
- 파일 잠금 문제 해결 방법
- `oc_file_locks` 테이블 관리
- 유지보수 모드 활용
- 파일 재스캔 방법

#### file_rm.md
- 강제 파일 삭제 작업
- 파일 시스템과 DB 동기화
- OCC 명령어를 통한 파일 재스캔

## App 종류 요약
- **txtoserver.py**: 여러 지점에서 하나의 서버로 데이터를 전송, WebDAV 프로토콜 사용
- **get_list.py**: Nextcloud에서 파일 목록 조회 및 다운로드
- **Docker Compose 스택**: 완전한 Nextcloud 서버 환경 구축
- **관리 도구**: 서버 유지보수 및 문제 해결 스크립트
- **플러그인**: 파일 보존 및 자동화 기능 확장

---

## Nextcloud 서버 설치 및 설정

### Docker Compose를 이용한 서버 설치
- 설치 및 설정 가이드
  - https://github.com/jeonghoonkang/BerePi/tree/master/apps/docker/docker_compose/nextcloud
  - 도커 컴포즈를 이용한 웹 서비스 실행 

### 신규 설치 후 필수 설정
- **VIRTUAL_HOST**: Nextcloud 접속 URL 입력
- **LETSENCRYPT_HOST**: SSL 인증서를 위한 URL 입력
- **LETSENCRYPT_EMAIL**: Let's Encrypt 알림 수신 이메일 입력

### HTTPS 문제 해결
로그인 후 페이지가 무한 대기하는 경우:
- **문제**: 아이디 입력 후 로그인 페이지에서 계속 대기
- **해결방법**: config.php 파일에 다음 설정 추가
  ```php
  'forcessl' => true,
  'overwriteprotocol' => 'https',
  ```
- **파일 위치**: `{volume-nextcloud}/config/config.php`

## Nextcloud 클라이언트 설정
### Ubuntu 클라이언트 
- 패키지 설치
  ```bash
  sudo apt install nextcloud-desktop
  ```
- 저장소: https://launchpad.net/~nextcloud-devs/+archive/ubuntu/client

### WebDAV 클라이언트 (Python)
- webdav3 라이브러리 사용
- 설정 파일(config.json)을 통한 인증 및 서버 정보 관리
- 프로그래밍 방식으로 파일 업로드/다운로드 가능

## Nextcloud 서버 설정
### Config.php 필수 설정
파일 위치: `volume/config/config.php`

중요 설정 항목:
```php
'overwrite.cli.url' => 'https://***.***.***:***',
'overwriteprotocol' => 'https',
```

참고: https://github.com/jeonghoonkang/BerePi/blob/0859bd0b6fe43aa6982d82b13f55e97919e72120/setup/howto/nextcloud_config_php.md

---

## 커맨드라인 관리 도구 (OCC)

### 파일 스캔 및 재등록
서버에 직접 파일 추가 후 Nextcloud DB에 등록:
```bash
sudo docker exec -it -u 33 nextcloud_app_1 php occ files:scan --all
```

### 앱 관리
앱 목록 확인:
```bash
sudo docker exec -it -u 33 {컨테이너명} php occ app:list
```

호환되지 않는 앱 비활성화:
```bash
sudo docker exec -it -u 33 {컨테이너명} php occ app:disable richdocumentscode
```

참고: https://docs.nextcloud.com/server/15/admin_manual/configuration_server/occ_command.html#apps-commands

### 파일 잠금 해제 및 스캔
파일 잠금 문제 해결 시:
1. 컨테이너 접속:
   ```bash
   sudo docker exec -it -uroot nextcloud /bin/bash
   ```

2. vim 설치 및 설정 파일 편집:
   ```bash
   apt update && apt install vim
   vim ./config/config.php
   ```

3. 다음 라인 추가:
   ```php
   'filelocking.enabled' => false,
   ```

4. 파일 스캔 실행:
   ```bash
   sudo docker exec -it -u 33 nextcloud php occ files:scan --all
   ``` 

---

## Nextcloud 백업 및 복원

### 백업 (Backup)

#### 1. 파일 시스템 백업
rsync를 이용한 Nextcloud 데이터 디렉토리 백업:
```bash
rsync -Aavx -e 'ssh -p22' --progress --partial nextcloud/ nextcloud-dirbkp_`date +"%Y%m%d"`/
```

#### 2. 데이터베이스 백업
MariaDB/MySQL 덤프:
```bash
mysqldump --single-transaction -h [server] -u [username] -p[password] [db_name] > nextcloud-sqlbkp_`date +"%Y%m%d"`.bak
```

예시:
```bash
# DB 컨테이너 IP 확인
sudo docker inspect nextcloud_db_1 | grep IP

# mysqldump 실행
mysqldump --single-transaction -h {IP} -u nextcloud -p{PW} nextcloud > nextcloud_sql_bk_new.bak
```

컨테이너 내부에서 백업 (권장):
```bash
mysqldump --single-transaction -v -h localhost -u** -p** nextcloud > /var/lib/mysql/**_nextcloud-sqlbkp_`date +"%Y%m%d"`.bak
```

### 복원 (Restore)

#### 1. 파일 시스템 복원
```bash
rsync -Aax nextcloud-dirbkp/ nextcloud/
```

#### 2. 데이터베이스 복원
DB 컨테이너 IP 확인:
```bash
sudo docker inspect {컨테이너명} | grep IP
```

기존 DB 삭제 및 재생성:
```bash
mysql -h [server] -u [username] -p[password] -e "DROP DATABASE nextcloud"
mysql -h [server] -u [username] -p[password] -e "CREATE DATABASE nextcloud"
```

UTF8 인코딩으로 DB 생성:
```bash
mysql -h [server] -u [username] -p[password] -e "CREATE DATABASE nextcloud CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"
```

백업 파일 복원:
```bash
mysql -h [server] -u [username] -p[password] [db_name] < nextcloud-sqlbkp.bak -v
```

예시:
```bash
mysql -h localhost -u nextcloud -p** nextcloud < db.bak -v
```

#### 3. Nextcloud 업그레이드
```bash
sudo docker exec -it -u 33 {컨테이너명} php occ upgrade
```

버전 확인:
```
version' => '21.0.2.1',
```
---

## CPU 플랫폼별 호환성 관리

### 업그레이드 불가능한 앱 비활성화
특정 CPU 아키텍처(예: ARM)에서 호환되지 않는 앱 처리:

앱 목록 확인:
```bash
sudo docker exec -it -u 33 {컨테이너명} php occ app:list
```

비호환 앱 비활성화:
```bash
sudo docker exec -it -u 33 {컨테이너명} php occ app:disable richdocumentscode
```

참고: https://docs.nextcloud.com/server/15/admin_manual/configuration_server/occ_command.html#apps-commands
---

## rsync 후 파일 스캔 절차

rsync로 파일을 직접 추가한 후 Nextcloud에 등록하는 과정:

### 1. 컨테이너 접속 및 설정
```bash
sudo docker exec -it -uroot nextcloud /bin/bash
```

### 2. 편집 도구 설치
```bash
apt update
apt install vim
# sudo가 없는 경우: apt update; apt install sudo
```

### 3. config.php 수정
```bash
vim ./config/config.php
```

다음 라인 추가:
```php
'filelocking.enabled' => false,
```

### 4. 파일 스캔 실행
```bash
sudo docker exec -it -u 33 nextcloud php occ files:scan --all
```

---

## Docker 컨테이너 관리 명령어

### 컨테이너 Bash 접속
```bash
docker exec -it {컨테이너명} /bin/bash
```

### 컨테이너 리소스 모니터링
실시간 CPU, 메모리, 네트워크 사용량 확인:
```bash
docker stats {컨테이너명}
```

### 컨테이너 로그 확인
```bash
docker logs -n 30 {컨테이너명}  # 최근 30줄
docker logs -f {컨테이너명}      # 실시간 로그
```

### DB 컨테이너 IP 확인
```bash
sudo docker inspect {컨테이너명} | grep IP
```

---

## 문제 해결 가이드

### 파일 잠금 문제
파일이 잠겨서 작업할 수 없는 경우:

1. 유지보수 모드 활성화:
   ```php
   // config/config.php
   'maintenance' => true,
   ```

2. DB에서 잠금 테이블 초기화:
   ```sql
   DELETE FROM oc_file_locks WHERE 1
   ```
   또는
   ```sql
   DELETE FROM oc_file_locks WHERE oc_file_locks.lock != 0
   ```

3. 유지보수 모드 비활성화

4. Cron 작업이 정상 동작하는지 관리자 페이지에서 확인

### 강제 파일 삭제 및 재스캔
파일 시스템에서 직접 파일 삭제 후 동기화:

1. 파일 삭제:
   ```bash
   sudo rm www/html/nextcloud/data/***/files/Backup_EV_center_ori_dir/image.png
   ```

2. 재스캔 (PHP 8.0은 아직 지원 안됨, 7.4 사용):
   ```bash
   sudo -u www-data php7.4 /var/www/html/nextcloud/occ files:scan --all
   ```

### Brute Force 공격 차단 해제
로그인 시도 횟수 초과로 차단된 IP 해제:

1. IP 주소 확인:
   ```bash
   sudo docker logs -n 30 {컨테이너명}
   ```

2. 차단 해제:
   ```bash
   sudo docker exec -it -u 33 {컨테이너명} php occ security:bruteforce:reset {IP주소}
   ```
   예: `php occ security:bruteforce:reset 192.168.1.100`

---

## 참고 자료

- [Nextcloud 공식 문서](https://docs.nextcloud.com/)
- [OCC 명령어 가이드](https://docs.nextcloud.com/server/15/admin_manual/configuration_server/occ_command.html)
- [WebDAV Python 클라이언트](https://github.com/ezhov-evgeny/webdav-client-python-3)
- [IOTstack Nextcloud 가이드](https://sensorsiot.github.io/IOTstack/Containers/NextCloud/)
- [Files Retention 플러그인](https://github.com/nextcloud/files_retention)
- [Automated Tagging 앱](https://apps.nextcloud.com/apps/files_automatedtagging)
