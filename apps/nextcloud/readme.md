# Nextcloud File Sync System

## 개요
이 디렉토리는 Nextcloud 파일 동기화 시스템과 관련된 다양한 응용 소프트웨어를 포함합니다. 
Nextcloud는 자체 호스팅 파일 동기화 및 공유 솔루션으로, 여러 클라이언트 도구, 서버 설정, 관리 스크립트, 플러그인 등을 제공합니다.

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
  - 대상 Nextcloud 디렉토리에 `YYYYMMDD_HHMMSS_devicename_clipboard.md` 파일 생성
  - `input.conf` 의 `[target]` 또는 `[destination]` 섹션 사용
  - 필요한 패키지(`streamlit`, `webdavclient3`)가 없으면 실행 중 자동 설치 시도
- **실행 방법**:
  - `python3 -m streamlit run apps/nextcloud/clipboardnextcloud.py`
  - 설정 파일을 기본값이 아닌 경로로 쓰려면 앱 실행 후 사이드바의 `Config path` 에서 변경
- **설정 파일**:
  - 기본 경로: `apps/nextcloud/input.conf`
  - 예시 섹션: `[target]`, `[settings]`

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
