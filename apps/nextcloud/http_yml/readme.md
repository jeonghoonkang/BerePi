# Nextcloud 저장 디렉토리 이전

시스템 디스크의 공간 부족을 해소하기 위해 Nextcloud의 `html` 디렉토리를 별도 디스크로 이전하는 절차입니다. 아래 명령은 수동 실행용이며, 이 문서의 존재가 이전 완료를 의미하지는 않습니다.

## 경로와 대상

| 항목 | 값 |
| --- | --- |
| 작업 디렉토리 | `/path/to/nextcloud_http` |
| Compose 파일 | `nextcloud.yml` |
| Compose 서비스 | `nextcloud` |
| 컨테이너 | `nextcloud_http` |
| 기존 호스트 경로 | `./volumes/nextcloud/html` |
| 새 호스트 경로 | `/mnt/nextcloud_disk/nextcloud/html` |
| 컨테이너 내부 경로 | `/var/www/html` |
| 컨테이너 데이터 경로 | `/var/www/html/data` |

이 문서의 `/path/to/nextcloud_http`와 `/mnt/nextcloud_disk`는 예시 경로입니다. 실제 Compose 디렉토리와 별도 디스크의 마운트 경로로 바꾸고, 복사 및 볼륨 설정에서 같은 대상 경로를 사용합니다.

`html` 전체를 복사하므로 사용자 파일, 설정, 앱을 함께 이전합니다. 컨테이너 내부 경로는 유지하며, `datadirectory` 설정을 변경하거나 파일 재검색을 실행할 필요는 없습니다. MariaDB 데이터는 이 절차에서 이동하지 않습니다.

## 1. 사전 확인

```bash
cd /path/to/nextcloud_http
mountpoint /mnt/nextcloud_disk
df -h /mnt/nextcloud_disk
sudo docker inspect nextcloud_http --format '{{json .Mounts}}'
```

`mountpoint`가 성공하고 대상 디스크의 여유 공간이 충분한 경우에만 진행합니다. 실제 디스크가 마운트되지 않은 상태에서 복사하면 시스템 디스크를 다시 채울 수 있습니다. `/etc/fstab` 등으로 재부팅 후에도 동일한 디스크가 자동 마운트되는지 확인합니다. `create_host_path: false`만으로 디스크 마운트를 보장하지는 않습니다.

이미 컨테이너가 새 경로를 사용하고 있다면 복사 단계를 다시 실행하지 말고 5번 검증부터 진행합니다. 오래된 원본을 새 저장소에 덮어쓰면 최신 파일이 손상될 수 있습니다.

이전 전 DB와 설정의 복구 가능한 백업을 확보합니다. 기존 설정 백업이 있다면 덮어쓰지 않습니다.

```bash
cp -an nextcloud.yml nextcloud.yml.before-move
```

이미 경로를 변경한 후 생성한 백업에는 새 경로가 들어 있으므로 복구 시 내용을 확인해야 합니다.

## 2. 유지보수 모드 및 서비스 중지

각 명령이 성공한 뒤 다음 명령을 실행합니다. 이 단계부터 작업 완료까지 Nextcloud 접속이 중단됩니다.

```bash
sudo docker exec -u www-data nextcloud_http php occ maintenance:mode --on
sudo docker stop nextcloud_http
```

별도로 운영하는 Nextcloud cron 또는 작업 컨테이너가 있다면 함께 중지하여 복사 중 쓰기를 막습니다. DB 컨테이너는 그대로 유지합니다.

## 3. 데이터 복사 및 비교

대상 디렉토리는 이번 이전 전용이어야 합니다. 기존에 다른 Nextcloud 인스턴스나 최신 데이터가 있다면 덮어쓰지 않습니다.

```bash
sudo mkdir -p /mnt/nextcloud_disk/nextcloud/html
sudo rsync -aHAX --numeric-ids --info=progress2 \
  ./volumes/nextcloud/html/ /mnt/nextcloud_disk/nextcloud/html/
```

원본 경로 끝의 `/`는 디렉토리 내용 전체를 복사한다는 뜻입니다. 소유권, 권한, 하드 링크, ACL 및 확장 속성을 보존합니다. 데이터 크기에 따라 복사에는 시간이 걸릴 수 있습니다.

복사가 정상 종료된 후 체크섬으로 내용을 비교합니다.

```bash
sudo rsync -aHAXnc --numeric-ids --delete --itemize-changes \
  ./volumes/nextcloud/html/ /mnt/nextcloud_disk/nextcloud/html/
```

출력 없이 정상 종료하면 비교 대상이 일치합니다. 차이나 오류가 출력되면 원인을 해결한 후 진행합니다. 위 비교 명령의 `-n`은 시험 실행이므로 실제 복사나 삭제는 하지 않습니다. 비교할 때 `-n`을 제거하지 않습니다.

## 4. Compose 볼륨 경로 변경

`nextcloud.yml`에서 `nextcloud` 서비스의 기존 항목:

```yaml
    volumes:
      - ./volumes/nextcloud/html:/var/www/html
```

을 삭제하거나 주석 처리하고 다음 설정으로 교체합니다. 기존 항목과 새 항목을 동시에 활성화하여 같은 `/var/www/html`에 두 경로를 연결하지 않습니다. `nextcloud_db` 서비스의 볼륨은 변경하지 않습니다.

```yaml
    volumes:
      - type: bind
        source: /mnt/nextcloud_disk/nextcloud/html
        target: /var/www/html
        bind:
          create_host_path: false
```

기존 항목을 기록용으로 남기려면 해당 줄 앞에 `#`을 붙입니다.

```yaml
      # - ./volumes/nextcloud/html:/var/www/html
```

Compose 설정에서 기존 항목을 제거해도 호스트의 `./volumes/nextcloud/html` 파일은 삭제되지 않습니다. 새 저장소에서 정상 동작과 백업을 확인할 때까지 원본을 보관합니다.

데이터 복사와 비교가 완료된 뒤 설정을 검사하고 기존 로컬 이미지로 컨테이너를 재생성합니다. 데이터 이전과 이미지 업그레이드는 함께 수행하지 않습니다.

```bash
sudo docker compose -f nextcloud.yml config --quiet
sudo docker compose -f nextcloud.yml up -d --no-deps --force-recreate --pull never nextcloud
```

`config --quiet`는 설정 구문 검사이며, 복사 완료나 올바른 디스크 사용까지 검증하지는 않습니다. 단순한 `docker restart`로는 변경된 볼륨 설정이 적용되지 않습니다.

## 5. 이전 결과 검증

```bash
sudo docker inspect nextcloud_http --format '{{json .Mounts}}'
sudo docker exec nextcloud_http df -h /var/www/html/data
sudo docker exec -u www-data nextcloud_http php occ status
```

다음을 확인합니다.

- `/var/www/html`의 호스트 원본이 `/mnt/nextcloud_disk/nextcloud/html`입니다.
- 데이터 경로의 파일시스템과 용량이 호스트에서 `df -h /mnt/nextcloud_disk`로 확인한 별도 디스크와 일치합니다.
- `occ status`에서 `installed: true`, `needsDbUpgrade: false`를 확인합니다.

호스트의 시스템 디스크(`/`)와 같은 파일시스템이 표시되면 여전히 시스템 디스크를 사용하고 있는 것입니다. Compose 경로와 호스트의 실제 마운트를 다시 확인합니다.

정상 확인 후 유지보수 모드를 해제합니다.

```bash
sudo docker exec -u www-data nextcloud_http php occ maintenance:mode --off
```

웹에서 로그인, 기존 파일 열기 및 다운로드, 새 파일 업로드를 확인합니다. 별도로 중지한 cron 또는 작업 컨테이너가 있다면 다시 시작합니다.

## 6. 기존 데이터 정리

복사만으로는 시스템 디스크 공간이 확보되지 않습니다. 새 저장소의 정상 동작과 별도 백업을 확인한 뒤 기존 `./volumes/nextcloud/html`을 정리해야 공간이 확보됩니다.

삭제 전 실제 컨테이너 마운트를 다시 확인합니다. `./volumes/nextcloud` 전체에는 DB 관련 디렉토리도 있으므로 전체를 삭제하지 않습니다. 이 문서에는 실수 방지를 위해 원본 삭제 명령을 포함하지 않습니다.

## 문제 발생 시 복구

새 저장소에서 사용자 쓰기를 허용하기 전 문제가 발견되었다면 다음 순서로 복구합니다.

1. `sudo docker stop nextcloud_http`로 컨테이너를 중지합니다.
2. `nextcloud.yml`의 `nextcloud` 볼륨을 기존 `./volumes/nextcloud/html:/var/www/html`로 되돌립니다.
3. `sudo docker compose -f nextcloud.yml config --quiet`로 검사합니다.
4. `sudo docker compose -f nextcloud.yml up -d --no-deps --force-recreate --pull never nextcloud`로 재생성합니다.
5. `occ status`와 기존 파일을 확인한 뒤 `sudo docker exec -u www-data nextcloud_http php occ maintenance:mode --off`를 실행합니다.

새 저장소에서 이미 업로드나 삭제가 발생했다면 기존 원본으로 바로 되돌리지 않습니다. 기존 파일과 현재 DB가 불일치할 수 있으므로 먼저 쓰기를 중지하고 최신 파일 및 DB를 보존한 뒤 복구해야 합니다.

---

# 기존 설치 메모

## Check this during Installation
- sudo chown -R 33:33 ./data
### database
- sudo docker exec -it nextcloud_db_http /bin/bash 
- show databases;
- CREATE database nextcloud;
- SELECT User, Host FROM mysql.user;
- CREATE USER 'nextcloud'@'%' IDENTIFIED BY '****';
- GRANT ALL PRIVILEGES ON nextcloud.* TO 'nextcloud'@'%'; 
- FLUSH PRIVILEGES;
- EXIT;
- sudo docker exec -it -u 33 nextcloud_http php occ files:scan --all
### photo
- 사진 파일 이동하여, occ 먼저 실행하고, memories 설치해야 함
