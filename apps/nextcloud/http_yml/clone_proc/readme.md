# 다른 서버로 Nextcloud 복제

`clone.py`는 현재 Nextcloud HTTP + MariaDB 두 컨테이너를 다른 IP 주소의 Linux 서버로 복제합니다. `export`, `transfer`, `restore` 순서로 실행합니다. 실제 사용자 데이터나 비밀번호는 이 디렉토리에 저장하지 않습니다.

**이 스크립트는 원본과 대상의 CPU 아키텍처가 동일한 경우에만 사용할 수 있습니다.** 예를 들어 x86_64 → x86_64 또는 ARM64 → ARM64 복제만 지원하며, x86_64 ↔ ARM64 복제는 지원하지 않습니다. CPU 제조사나 모델명이 같아야 한다는 의미는 아닙니다.

## 복제 범위

- 실제 실행 중인 컨테이너의 마운트에서 `html` 전체와 MariaDB `/var/lib/mysql` 데이터를 찾습니다. 이전 이동 작업에서 남은 오래된 `html`이나 불완전한 백업을 사용하지 않습니다.
- Nextcloud 파일, 앱, 설정, DB 데이터, DB의 `/config` 및 `/backup` 마운트가 있으면 함께 복사합니다.
- 실제 실행 중인 Docker 이미지를 `docker image save`로 저장하고 대상에서 로드합니다. `latest`를 새로 내려받거나 DB/Nextcloud 버전을 변경하지 않습니다.
- 원본 Compose 파일은 참고용으로 보관하고, 대상 경로와 포트에 맞는 새 `nextcloud.yml`을 생성합니다.
- 대상 IP/포트에 맞춰 `trusted_domains`, `overwritehost`, `overwriteprotocol`, `overwrite.cli.url`을 설정하고 이전 프록시 관련 설정을 정리합니다.
- 원본 계정, 비밀번호, 파일 공유 및 앱 설정도 복사됩니다. 새 서비스가 빈 Nextcloud로 초기화되는 방식이 아닙니다.

대상은 동일 CPU 아키텍처의 Linux + Docker Engine + Docker Compose v2 환경이어야 합니다. 직접 HTTP 접속만 지원합니다. HTTPS, 도메인, 리버스 프록시, 방화벽, 라우터 포트 포워딩 및 외부 DNS는 별도 설정입니다. 공개 인터넷에 노출하기 전에는 HTTPS와 접근 정책을 구성하세요.

Redis, S3/object storage, 별도 데이터 경로, 추가 컨테이너 마운트, 기본 이미지와 다른 실행 명령은 자동 복제 대상이 아니며 확인 가능한 경우 사전 검사에서 중단합니다. LDAP, SMTP, 외부 저장소, 호스트 cron/systemd 작업처럼 컨테이너 밖에 있는 서비스와 스케줄은 별도로 이전해야 합니다. 외부 연동 설정은 복사된 앱에 남을 수 있으므로 중복 메일 발송이나 외부 작업 실행도 확인하세요.

## 작업 전 조건

1. 양쪽 서버에 `python3`(3.8 이상), `docker`, `docker compose`, `rsync`, `dmesg`가 필요합니다. 전송 시 `ssh`도 필요합니다.
2. 파일 소유권과 ACL 보존을 위해 root 또는 sudo로 실행합니다. 비밀번호를 스크립트나 명령 인자로 입력하지 않습니다.
3. 복제 묶음과 대상 데이터는 Git 저장소 밖의 별도 디스크에 둡니다. 디스크는 재부팅 후에도 동일 경로에 마운트되어야 합니다.
4. 원본과 대상 모두 이 부팅의 커널/스토리지 오류가 없어야 합니다. 기존 서버에서 반복된 page fault/Oops가 남아 있으면 스크립트는 중단합니다. 속도 제한이 커널 오류를 해결해 주는 것은 아닙니다.
5. 원본의 두 컨테이너가 실행 중이고 DB 및 Nextcloud 진단이 정상이어야 합니다. 앱이 사용하는 DB 호스트는 `nextcloud_db` 또는 `nextcloud_db:3306`, DB 자격 증명은 현재 구성의 `MYSQL_*` 환경변수 형식을 전제로 합니다.
6. 별도 cron/worker, 호스트 스크립트 등 데이터에 쓰는 작업은 먼저 중지합니다. 같은 데이터를 마운트한 다른 실행 중 컨테이너가 발견되면 export를 거부합니다.
7. export에는 데이터+이미지 크기 및 15% 여유 공간이 필요합니다. 대상에는 전송 묶음 외에 실제 데이터 사본과 Docker 이미지 저장 공간이 더 필요합니다.

## 1. 원본 서버에서 export

아래 경로는 모두 예시입니다. `--compose`에는 저장소의 예시 파일이 아니라 실제 운영 Compose 파일을 지정합니다.

```bash
sudo python3 clone.py export \
  --compose /path/to/running/nextcloud.yml \
  --mount /mnt/source_disk \
  --output /mnt/source_disk/nextcloud-clone-20260911 \
  --app nextcloud_http \
  --db nextcloud_db_http \
  --bwlimit 51200
```

`--output`은 아직 존재하지 않는 디렉토리여야 합니다. 이전에 실패한 묶음을 덮어쓰지 않습니다. `--bwlimit` 단위는 KiB/s이며 기본값은 약 50MiB/s입니다.

작업 순서는 다음과 같습니다.

1. 마운트, 상태, 여유 공간, 커널 로그를 검사합니다.
2. 현재 이미지를 저장합니다. 이 동안 서비스는 계속 실행됩니다.
3. 유지보수 모드를 켜고 앱을 중지한 다음 DB를 정상 종료합니다.
4. 서비스가 중지된 상태에서 HTML과 DB 파일을 복사합니다. 이 구간 동안 접속이 중단됩니다. 데이터가 크면 오래 걸릴 수 있습니다.
5. 복사본을 비교하고 원본 DB, 앱 순서로 다시 시작합니다. 기존 유지보수 모드가 꺼져 있었다면 다시 해제합니다.
6. 모든 과정이 성공해야 `READY` 표시를 생성합니다. 실패하면 `INCOMPLETE`가 남아 restore가 거부됩니다.

원본 파일은 삭제하지 않습니다. `rsync --remove-source-files`나 실제 삭제 동기화는 사용하지 않습니다. 비교 단계의 `--delete`는 반드시 `-n`과 함께 사용되며, 새 스냅샷에만 적용하는 읽기 전용 검사입니다. 이전에 부분 이동된 백업 디렉토리에 이 비교를 적용하지 않습니다.

기본 비교는 파일 크기, 수정 시각, 속성 기준입니다. 전체 내용 체크섬 비교가 필요하면 `--verify-content`를 추가합니다. 그만큼 서비스 중단 시간이 길어집니다. 정상적인 rsync 전송 성공이 손상된 원본 데이터나 하드웨어 문제까지 배제하는 것은 아닙니다.

Ctrl+C, 명령 실패 시에도 원본 서비스 복구를 시도합니다. 강제 종료, 시스템 정지, 전원 차단 시에는 복구 코드가 실행되지 않을 수 있습니다. 그 경우 다음 순서로 원본을 확인합니다.

```bash
sudo docker start nextcloud_db_http
sudo docker logs --tail 50 nextcloud_db_http
# DB가 ready for connections 상태가 된 뒤 실행
sudo docker start nextcloud_http
sudo docker exec -u www-data nextcloud_http php occ status
# 작업 전 유지보수 모드가 꺼져 있었을 때만 실행
sudo docker exec -u www-data nextcloud_http php occ maintenance:mode --off
```

완성된 묶음에는 다음 내용이 있습니다.

```text
nextcloud-clone-20260911/
  READY
  clone.py
  manifest.json               # 이미지 ID, 환경변수 및 자격 증명
  images.tar                  # 실행 중이던 정확한 이미지
  metadata/source-compose.yml # 원본 설정 (비밀번호 포함 가능)
  data/html/
  data/db/
  data/db_config/              # 해당 마운트가 있을 때
  data/db_backup/              # 해당 마운트가 있을 때
```

묶음 최상위는 권한 `0700`, 메타데이터는 `0600`으로 생성합니다. 이 묶음은 암호화된 파일이 아니며 실제 개인정보, Nextcloud 비밀키 및 비밀번호가 들어 있습니다. Git에 추가하거나 공개 공유하지 마세요.

## 2. SSH로 대상 서버에 전송

예시 IP `192.0.2.20`을 실제 대상 IP로 바꿉니다. 대상 부모 디렉토리가 먼저 존재하고 올바른 디스크가 마운트되어 있어야 합니다. root SSH 키 인증이 이미 구성되어 있고 서버 호스트 키가 확인된 환경에서 사용합니다. 스크립트가 root 로그인이나 SSH 정책을 변경하지는 않습니다.

```bash
sudo python3 clone.py transfer \
  --bundle /mnt/source_disk/nextcloud-clone-20260911 \
  --ssh root@192.0.2.20 \
  --remote-dir /mnt/target_disk/nextcloud-clone-20260911 \
  --bwlimit 51200
```

전송은 SSH로 암호화됩니다. 파일 소유권과 권한을 보존하고 `READY`를 마지막에 전송합니다. 대상 디렉토리가 이미 있으면 중단합니다. 실패한 전송은 다른 새 디렉토리로 다시 시도하고, 불완전한 묶음을 실행하지 마세요. root SSH가 허용되지 않는 환경에서는 관리자가 승인한 별도 전송 방식으로 동일 소유권/권한을 보존하여 복사해야 합니다.

## 3. 대상 서버에서 restore

다른 서버에서 실행해야 하며, 같은 이름의 기존 컨테이너를 덮어쓰지 않습니다. `--destination`도 새 디렉토리여야 합니다. `--origin`에는 실제 대상 IP와 서비스 포트를 입력합니다.

```bash
sudo python3 /mnt/target_disk/nextcloud-clone-20260911/clone.py restore \
  --bundle /mnt/target_disk/nextcloud-clone-20260911 \
  --mount /mnt/target_disk \
  --destination /mnt/target_disk/nextcloud_22080 \
  --origin http://192.0.2.20:22080 \
  --bwlimit 51200
```

원본 스냅샷은 보관하고 새로운 운영 디렉토리로 복사합니다. 이미지 로드 후 원본과 이미지 ID 및 아키텍처를 비교합니다. DB가 준비된 다음 앱을 시작하고 대상 주소를 설정한 뒤 유지보수 모드를 해제합니다. 기존 사용자 계정으로 접속할 수 있습니다.

생성된 `nextcloud.yml`은 JSON 형식으로 직렬화한 유효한 YAML 문서입니다. Compose가 읽을 수 있으며, 환경변수의 `$` 문자가 Compose 변수로 잘못 치환되지 않도록 처리합니다. 파일에는 비밀번호가 포함되므로 `0600` 권한을 유지합니다.

실패하면 해당 복제 컨테이너만 중지하고 대상 파일을 보존합니다. 원본 서비스나 전송 묶음은 삭제하지 않습니다. 원인을 확인한 뒤 실패한 대상 컨테이너/디렉토리는 별도로 정리하거나 보관해야 재시도할 수 있습니다.

## 4. 동작 확인 및 전환

```bash
sudo docker exec nextcloud_http df -h /var/www/html/data
sudo docker exec nextcloud_db_http df -h /var/lib/mysql
sudo docker exec -u www-data nextcloud_http php occ status
sudo docker compose -p nextcloud-clone \
  -f /mnt/target_disk/nextcloud_22080/nextcloud.yml ps
curl --fail http://192.0.2.20:22080/status.php
```

대상 외부의 브라우저에서 로그인, 기존 파일 다운로드, 새 파일 업로드, 앱 및 공유 링크를 검사합니다. 방화벽과 접근 경로는 자동으로 열지 않습니다. HTTP 상태 확인만으로 전체 파일의 무결성을 보장하지는 않습니다.

이 작업은 한 시점의 복제입니다. export 후 원본에서 추가된 변경은 대상에 자동 반영되지 않습니다. 최종 서비스 전환 시 원본 쓰기를 중지하고 마지막 스냅샷을 생성하는 일정을 잡으세요. 검증 중 원본과 복제본을 같은 동기화 클라이언트로 동시에 운영하지 않습니다. 기존 URL이 바뀌므로 클라이언트 주소와 공유 링크도 확인해야 합니다.

## 검증 및 참고

코드의 비파괴 테스트:

```bash
python3 -m unittest discover -s tests -v
python3 clone.py --help
```

- [Nextcloud 백업 문서](https://docs.nextcloud.com/server/stable/admin_manual/maintenance/backup.html)
- [Nextcloud 서버 이전 문서](https://docs.nextcloud.com/server/stable/admin_manual/maintenance/migrating.html)
- [Docker 이미지 저장](https://docs.docker.com/reference/cli/docker/image/save/)
- [Docker 이미지 로드](https://docs.docker.com/reference/cli/docker/image/load/)

이 스크립트는 서비스를 실제 복제하여 검증하기 전까지 운영 환경 전체에 대한 동작 보증이 아닙니다. 실제 export/transfer/restore는 명시적으로 실행할 때만 수행됩니다.
