# Ubuntu 장비 최초 실행

장비 전원을 켜고 `install.sh`를 한 번 실행하면 GitHub의
`jeonghoonkang/BerePi` 저장소 `master`에서 fleet-ocr 코드를 받아 설치하고,
Nextcloud 동기화 → OCR → 결과 업로드를 즉시 실행합니다.
다운로드와 설치에는 인터넷 연결이 필요하며 Ubuntu/Debian의 systemd 환경에서 실행합니다.
기본 실행은 클라이언트에서 ID를 직접 입력하고 저장합니다. ID 서버 접속은 선택 사항입니다.
`install.sh`와 장비 설정을 복사하면 되며, 서버 발급·인증을 선택할 때는 `register_device.py`도 필요합니다.
코드 다운로드와 Nextcloud/OCR 서버 접속은 기존대로 필요합니다.

## ID 발급 서버 주소와 실행 경로 설정

클라이언트의 `/root/sononet-device.env`에서 ID 발급·인증 서버 주소와 API 경로를 지정합니다.

```bash
# 상태 보고와 주기적인 충돌 검사 서버
FLEET_API_URL=https://fleet.example.com
# ID 발급·인증 서버 주소: 포트와 프록시 접두 경로도 지정 가능
FLEET_ID_API_URL=https://id.example.com:8443/fleet
# 자동 발급 코드가 실행되는 API 경로
FLEET_ID_REGISTER_PATH=/v1/devices/register
# 수동으로 입력한 ID의 인증 API 경로
FLEET_ID_MANUAL_PATH=/v1/devices/manual
```

위 설정에서 자동 발급 요청은 `https://id.example.com:8443/fleet/v1/devices/register`,
수동 ID 인증 요청은 `https://id.example.com:8443/fleet/v1/devices/manual`로 전송됩니다.
API 경로는 `/`로 시작하며 서버 주소 뒤에 붙습니다. 서버 파일시스템의 `.py` 경로가 아니라
발급 코드가 처리하는 **HTTP API 경로**를 설정하는 것입니다.

`FLEET_ID_API_URL`이 비어 있거나 없으면 기존처럼 `FLEET_API_URL`을 사용합니다.
두 경로도 비어 있으면 각각 `/v1/devices/register`, `/v1/devices/manual`을 사용합니다.
설치 시 최종 설정이 `/etc/sononet/device.env`에 저장되어 재실행에도 사용됩니다.
이미 유효한 장비 ID·토큰이 있으면 주소 설정만 바꿔도 발급 요청을 다시 보내지는 않습니다.

서버나 리버스 프록시가 설정한 경로를 실제 API로 연결해야 합니다. 클라이언트 설정만으로
서버 라우트가 생성되지는 않습니다. ID 서버를 상태 보고 서버와 분리하면 발급한 토큰을
상태 보고 서버에서도 검증할 수 있도록 같은 `FLEET_HMAC_SECRET`과 일관된 장비 DB를 사용합니다.
`FLEET_ENROLLMENT_TOKEN`은 ID 발급·인증 서버에 설정된 등록 전용 토큰입니다.
HTTPS만 지원하며 인증정보가 다른 주소로 전달되지 않도록 리다이렉트는 따르지 않습니다.

자동 발급의 재시도 키는 ID 서버 주소에 묶입니다. 이미 등록한 장비의 서버 주소를 바꿔
재등록하면 오류로 중단되므로 기존 `registration.json`을 삭제하여 우회하지 마십시오.
동일 서버의 API 경로만 바꾸는 경우에는 기존 재시도 키를 유지합니다.

## ID 직접 입력과 주기적인 충돌 확인

`SONONET_ID_MODE`를 생략하거나 비워도 기본값은 `manual`입니다. 장비 ID를 설정 파일에 직접 입력하거나,
다음처럼 명령행에서 지정할 수 있습니다.

```bash
sudo bash install.sh /root/sononet-device.env --device-id LAB-001
```

`--device-id`는 설정 파일의 모드·ID를 덮어쓰고 수동 모드로 저장합니다.
터미널에서 수동 모드로 실행했는데 ID가 비어 있으면 입력을 요청합니다.
무인 실행에서는 ID가 없으면 종료하며 자동 번호로 대체하지 않습니다.
실행 화면에 서버에서 ID를 할당받을 수도 있다는 안내와 `--server-id` 사용법을 출력합니다.
ID는 영문/숫자로 시작하는 1~128자의 영문·숫자·점·밑줄·하이픈 문자열입니다.

```bash
SONONET_ID_MODE=manual
SONONET_DEVICE_ID=LAB-001
SONONET_FETCH_DEVICE_TOKEN=0
DEVICE_TOKEN=
FLEET_ENROLLMENT_TOKEN=
```

기본값 `SONONET_FETCH_DEVICE_TOKEN=0`에서는 토큰이 없어도 ID 서버에 접속하지 않고
입력한 ID를 저장해 설치·OCR을 진행합니다. `FLEET_API_URL`과 `DEVICE_TOKEN`이 없으면
서버 상태 보고·충돌 확인은 보류되며, 해당 기능을 사용할 수 없다는 안내를 출력합니다.
이때 충돌 상태는 `clear`가 아닌 `unverified`로 기록됩니다.

주기적인 충돌 확인을 사용하려면 상태 보고 서버의 `FLEET_API_URL`과 해당 ID의
유효한 `DEVICE_TOKEN`을 설정하십시오. 입력한 ID의 인증 토큰만 서버에서 받으려면
`SONONET_FETCH_DEVICE_TOKEN=1`을 명시적으로 설정하고, `DEVICE_TOKEN`은 비우며,
ID 서버 주소와 실제 `FLEET_ENROLLMENT_TOKEN`을 설정한 후 설치기를 다시 실행합니다.
이때만 수동 ID 인증 API를 호출하며, 중복된 ID도 거부하거나 변경하지 않습니다.
이미 해당 ID의 유효한 `DEVICE_TOKEN`이 있으면 인증 토큰 요청을 생략합니다.
설정 파일에서 ID를 변경할 때는 새 ID에 맞는 토큰을 설정하거나 위의 선택적 인증 요청을 사용하십시오.
명령행 `--device-id`로 ID를 변경하면 이전 토큰은 자동으로 비워집니다.

각 장비는 최초 heartbeat 때 `/var/lib/sononet/instance-id`에 무작위 내부 식별자를 만들고
재부팅 후에도 재사용합니다. 사용자가 입력한 ID가 같더라도 내부 식별자가 다르면
서로 다른 장비로 구분합니다. 호스트 이름이나 IP 주소가 같아도 구분할 수 있습니다.

- 기존 heartbeat 타이머(기본 5분 + 무작위 지연)가 보고할 때마다 서버에서 검사합니다.
- 기본적으로 **최근 24시간 안에 동일한 ID를 보고한 내부 식별자가 2개 이상**이면 충돌입니다.
  서버 `.env`의 `FLEET_ID_CONFLICT_WINDOW_SECONDS`로 판정 기간을 조정합니다(최소 60초).
- 두 번째 장비는 보고 응답으로 바로 충돌을 받고, 첫 번째 장비는 다음 보고 때 받습니다.
- 충돌 시 OCR은 계속 실행하며 ID를 자동으로 바꾸지 않습니다.
  클라이언트 journal과 서버 로그에 `device_id_conflict` 경고를 기록합니다.
- `/var/lib/sononet/id-conflict.json`에 최근 결과(`conflict`/`clear`/`unverified`)를 저장합니다.
  통신 실패나 구버전 서버 응답은 `unverified`이며, 충돌이 없다고 판단하지 않습니다.
- 한 장비의 ID를 수정하면 그 장비의 다음 heartbeat 때 기존 ID 사용 기록이 이동합니다.
  보고가 끊긴 장비는 판정 기간이 지나면 비교 대상에서 빠집니다. 다시 보고하면 재검사합니다.

클라이언트 확인:

```bash
journalctl -u sononet-heartbeat.service -n 100 --no-pager
sudo cat /var/lib/sononet/id-conflict.json
```

관리자 서버 조회(장비 ID, 충돌 장비별 내부 식별자·호스트명·최근 수신 Unix 시각):

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" https://fleet.example.com/v1/id-conflicts
```

같은 중앙 서버에 보고하는 장비끼리 비교하며, 내부 식별자를 보내지 않는 구버전 장비는
비교할 수 없습니다. 서버와 클라이언트를 모두 업데이트해야 합니다.
`/var/lib/sononet/instance-id`를 다른 장비나 출하 이미지에 복제하면 서로 구분할 수 없으므로
장비별로 생성되도록 하십시오. 같은 장비를 재설치할 때는 이 파일을 보존하십시오.
이 검사는 설치별 식별자 기반의 운영 충돌 감지이며 하드웨어 신원 인증은 아닙니다.
동일한 ID를 쓰면 기본 Nextcloud 경로도 같아지므로, 데이터 분리가 필요하면
`NEXTCLOUD_REMOTE_PATH`를 장비별로 지정하십시오.

## 서버 인증 설정 및 선택적 자동 번호 발급

서버의 `central/.env`에 `FLEET_ENROLLMENT_TOKEN`을 설정합니다.
`openssl rand -hex 32`로 새 값을 생성하고, 관리자 토큰·HMAC 비밀값과는 다른 값을 사용합니다.
서버에서 변경된 API를 먼저 배포합니다.

```bash
cd central
docker compose up -d --build
```

장비 설정에도 같은 `FLEET_ENROLLMENT_TOKEN`과 HTTPS `FLEET_ID_API_URL`을 넣습니다.
서버 자동 번호 발급을 선택하려면 다음과 같이 실행합니다.

```bash
sudo bash install.sh /root/sononet-device.env --server-id
```

`--server-id`는 이번 실행을 `auto` 모드로 바꾸고 기존 ID·토큰을 비운 후 서버에 요청합니다.
`--device-id`와 함께 사용할 수 없습니다. 설정 파일에서 `SONONET_ID_MODE=auto`를 지정하고
`SONONET_DEVICE_ID`, `DEVICE_TOKEN`을 비워 두는 방법도 지원합니다.
중앙 HMAC 비밀값이나 관리자 토큰은 장비에 배포하지 않습니다.

1. 클라이언트가 장비별 무작위 등록 키를 `/etc/sononet/registration.json`에 먼저 저장합니다(0600).
2. HTTPS `POST /v1/devices/register`로 등록 키를 보내며 등록 전용 토큰으로 인증합니다.
3. 서버는 SQLite 트랜잭션 안에서 `SN-000001` 형식의 사용하지 않은 번호를 발급하고,
   장비 번호와 장비 전용 인증 토큰을 응답합니다. 등록 키는 해시로만 저장합니다.
4. 클라이언트는 응답을 `/etc/sononet/device.env`에 저장하고 설치·OCR 실행을 계속합니다.

동시 요청은 DB 쓰기 잠금과 고유 제약조건으로 처리합니다. 응답이 유실되면 같은 등록 키로
최대 3번 요청하며, 같은 키에는 같은 번호가 반환됩니다. 모든 재시도가 실패하면 설치를
중단하고 등록 키를 보존하므로 다음 실행에서 이어갈 수 있습니다.
설치된 설정으로 재실행할 때는 저장된 장비 번호와 토큰을 그대로 사용합니다.

중복 방지는 **동일한 중앙 DB를 사용하는 자동 등록 장비**에 적용됩니다.
`fleet-data` 볼륨(번호 발급 기록)을 유지하고 일관된 SQLite 백업을 보관하십시오.
독립 DB를 가진 서버 여러 대에서는 각각 같은 번호가 발급될 수 있습니다.
기존 heartbeat/event에 기록된 수동 번호는 예약됩니다. 아직 서버에 보고하지 않은 수동 번호는
알 수 없으므로 자동 등록을 활성화하기 전에 기존 장비의 heartbeat를 수집해야 합니다.
수동 입력 모드는 중복을 허용하며 위의 주기적인 충돌 검사를 사용합니다.

`registration.json`과 설치된 `device.env`는 장비별 파일입니다. 출하 이미지에 복제하면
같은 장비로 인식되므로 넣지 마십시오. OS 재설치 시 기존 등록 키 또는 장비 설정을 복원하면
번호를 유지할 수 있고, 모두 잃어버리면 새 장비로 등록됩니다. 등록 키는 하드웨어 신원을
증명하는 값이 아니라 이 설치를 식별하는 비밀값입니다.

서버의 등록 전용 토큰을 비우면 신규 등록이 중지되며, 기존 장비의 heartbeat/OCR은 계속됩니다.
이 토큰을 변경하면 새로 등록하거나 등록을 재시도하는 장비에도 변경된 값을 배포해야 합니다.
heartbeat 전에도 발급된 번호를 관리자 API에서 확인할 수 있습니다.

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" https://fleet.example.com/v1/registrations
```

## 최초 실행

1. `install.sh`, `device.env.example`을 Ubuntu 장비에 복사합니다.
   서버 발급·인증을 선택하면 `register_device.py`도 복사합니다.
2. 설정 파일을 만들고 실제 서버 주소와 장비 인증 정보를 입력합니다.

   ```bash
   sudo install -m 0600 device.env.example /root/sononet-device.env
   sudoedit /root/sononet-device.env
   ```

   `NEXTCLOUD_URL`, `NEXTCLOUD_USER`, `NEXTCLOUD_APP_PASSWORD`,
   `OCR_API_BASE_URL`, `OCR_API_KEY`를 설정합니다.
   ID 서버 주소·등록 토큰은 서버 발급·인증을 선택할 때만 설정합니다.
   `FLEET_API_URL`과 `DEVICE_TOKEN`은 상태 보고·충돌 확인을 사용할 때 설정합니다.
   수동 모드에서는 `SONONET_DEVICE_ID`를 입력합니다.
   `NEXTCLOUD_REMOTE_PATH`가 비어 있으면 `/Fleet/<장비 ID>`를 사용합니다.
   설치 화면에 출력되는 경로 아래에 Nextcloud `inbox` 폴더가 필요합니다. 아직 없다면
   해당 폴더를 생성한 후 같은 설치 명령을 다시 실행하십시오.
   이 설치기는 Nextcloud 사용자나 폴더를 생성하지 않습니다.
   인증이 없는 OCR 서버를 사용하는 경우에만 `OCR_API_KEY`를 빈 값으로 둡니다.
   `SONONET_DEVICE_ID`와 해당 ID의 `DEVICE_TOKEN`을 모두 지정하면 서버 인증 요청을 생략합니다.

3. 최초 설치 및 실행:

   ```bash
   sudo bash install.sh /root/sononet-device.env --device-id LAB-001
   ```

   인수를 생략하면 `/root/sononet-device.env`를 사용합니다.
   설치된 설정은 `/etc/sononet/device.env`에 root 전용 권한으로 저장됩니다.
   설정 파일은 root 권한으로 읽는 셸 코드이므로 관리자가 준비한 파일만 사용하십시오.

## 실행 이후

- 최초 설치 직후 OCR 파이프라인을 실행합니다. heartbeat는 서버 주소·장비 토큰이 있으면 전송합니다.
- 재부팅 후에는 systemd 타이머가 자동으로 OCR(10분), heartbeat(5분),
  Git 업데이트(30분)를 실행합니다. 각 타이머에는 부팅 지연과 무작위 지연이 있습니다.
- 실패하면 스크립트가 0이 아닌 종료 코드로 종료합니다. 네트워크나 설정을 수정한 뒤
  같은 명령을 다시 실행하면 설치를 재적용합니다. 이미 설치된 타이머는 유지됩니다.
- 설치된 설정으로 다시 실행하려면 `sudo bash install.sh /etc/sononet/device.env`를 사용합니다.

```bash
systemctl list-timers 'sononet-*'
journalctl -u sononet-pipeline.service -n 100 --no-pager
journalctl -u sononet-heartbeat.service -n 100 --no-pager
journalctl -u sononet-ansible-pull.service -n 100 --no-pager
```

## 다운로드 서버 변경

`SONONET_REPO_URL`과 `SONONET_REPO_BRANCH`로 다른 Git 서버를 지정할 수 있습니다.
`SONONET_PLAYBOOK_PATH`는 저장소 루트 기준 플레이북 경로입니다.
fleet-ocr만 별도 저장소로 운영하면 이 값을 `local.yml`로 설정합니다.
`FLEET_API_URL`은 장비 등록·상태 수집 서버 주소이며 코드 다운로드 주소와는 별개입니다.
사설 Git 저장소는 설치 전에 root 계정의 읽기 전용 Git 인증을 준비해야 합니다.

이 클라이언트와 하위 경로 업데이트 지원 변경이 다운로드 대상 브랜치에 반영된 후
장비에서 실행하십시오.

## 개발 검증

프로젝트 루트(`ubuntu-fleet-ocr`)에서 테스트 의존성을 설치한 가상환경으로 실행합니다.

```bash
python3 -m venv /tmp/fleet-ocr-test-venv
/tmp/fleet-ocr-test-venv/bin/pip install -r tests/requirements.txt
/tmp/fleet-ocr-test-venv/bin/python -m unittest discover -s tests -v
```

서버의 실제 SQLite/FastAPI로 동시 발급·재시도·수동 ID 충돌과 해제를 검증합니다. 클라이언트 HTTP 요청은
테스트 API에 연결하고, 설치 명령은 모의 실행하므로 실제 Ubuntu 설치·TLS 서버 접속은
운영 환경에서 별도 확인해야 합니다.
