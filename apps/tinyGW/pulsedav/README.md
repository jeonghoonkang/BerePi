# PulseDAV

호스트 상태를 Markdown 파일로 만들고 WebDAV 서버로 전송하는 도구입니다.

## 수집 항목

- CPU 상태
- 내부 IP 주소
- Public IP 주소
- 내부 GW 주소
- DDNS 이름
- SSH 포트
- GPU 리스트
- GPU 스펙
- HDD 공간
- 서비스 중 사용자가 실행한 서비스
- `screen` 리스트
- `crontab`
- Docker 운영 상태

## 동작

- WebDAV 루트 디렉토리 하위에 `tinyGW` 디렉토리를 만들고, 그 아래에 자신의 호스트명 디렉토리를 만듭니다.
- `webdav.sub` 을 지정하면 `tinyGW/<sub>/<호스트명>/` 아래에 저장합니다. 배열로 여러 값을 지정하면 각 `sub` 경로마다 같은 `pulse_YYYYMMDD_HHMMSS.md` 파일을 추가로 만듭니다.
- 전송할 때마다 `pulse_YYYYMMDD_HHMMSS.md` 파일을 새로 만듭니다.
- 각 노드의 `sender.py`가 자기 호스트 폴더에 업로드한 Markdown 보고서(`pulse_YYYYMMDD_HHMMSS.md`, `iptime_YYYYMMDD_HHMMSS.md`)를 정리합니다. 로컬 파일이나 다른 노드의 보고서는 삭제하지 않습니다. 이 보고서 중 36개월보다 오래된 파일은 자동 삭제합니다.
- 일반 상태 보고서와 ipTIME 보고서 모두 전송 전에 현재 호스트의 원격 폴더 내 파일 용량, 서버 여유 공간, 새 보고서의 바이트 수를 확인하고 출력합니다.
- 서버 여유 공간이 5GB(5,000,000,000바이트) 이하이면 **가장 오래된 Markdown 보고서를 먼저 삭제하고 최신 보고서를 업로드**하는 순환 저장 방식으로 동작합니다. 오래된 파일 한 개의 크기가 새 보고서 이상이면 한 개만 지웁니다. 작으면 새 보고서 크기만큼 확보될 때까지 다음으로 오래된 보고서를 추가로 지워 이번 전송으로 사용량이 늘지 않도록 합니다. 이미 5GB 미만일 때는 5GB까지 복구하려고 대량 삭제하지 않습니다.
- 여유 공간이 5GB보다 많아도 이번 업로드로 5GB 아래로 내려갈 경우에는 필요한 만큼 정리합니다. 36개월 이내의 보고서도 용량 확보 대상입니다. 여러 `sub` 경로는 각 업로드 직전에 다시 확인합니다.
- 서버 여유 공간은 Nextcloud serverinfo API의 `ocs.data.nextcloud.system.freespace` 정수 바이트 값으로 확인합니다. `webdav.hostname`(Nextcloud 설치 하위 경로 포함)에 `/ocs/v2.php/apps/serverinfo/api/v1/info?format=json&skipApps=true&skipUpdate=true`를 붙이고 기존 WebDAV 인증/SSL 설정으로 GET 요청합니다. serverinfo 앱이 활성화되어 있어야 하며 현재 구현은 관리자 계정 인증이 필요합니다. WebDAV의 무제한 할당량 값 `-3`은 사용하지 않습니다. `null`, 음수, 비정상 응답이나 권한 오류이면 전송을 중단합니다. 서버 여유 공간과 사용자 계정 할당량은 다르며, 외부 저장소 사용 시 이 값이 업로드 대상 저장소를 나타내는지 확인해야 합니다.
- 용량 조회만 시험하려면 `python3 sender.py --config this.setting.json --dry-run`을 실행하세요 (`--once`와 함께 사용 가능). HTTP 상태, `nextcloud.system.freespace` 값, 여유 바이트/GB 및 5GB 이하 여부를 출력합니다. 원격 폴더 생성, 삭제·업로드, 보고서 수집, Telegram 전송 및 상태 저장은 실행하지 않습니다. 모든 조회가 성공하면 종료 코드 0, 실패하면 1입니다. 여유 공간 0바이트도 조회 자체는 성공이며 업로드 가능 여부를 보장하지 않습니다.
- 삭제 후 서버 여유 공간을 다시 조회해 실제 확보 여부를 확인합니다. 용량 정보를 얻을 수 없거나, 이전 보고서만으로 공간이 부족하거나, 휴지통 등으로 삭제 후 공간이 늘지 않으면 오류를 표시하고 전송을 중단합니다. 용량 부족을 미리 알 수 있으면 파일을 삭제하지 않습니다.
- 용량 확보 대상에서 다른 호스트, 하위 폴더, 일반 파일, 이번에 업로드할 경로는 제외합니다. 동시 실행이나 다른 클라이언트가 검사 이후 사용하는 공간까지 예약하는 기능은 아닙니다.
- 부팅 후 첫 전송 메세지에는 `부팅한 직후`를 포함합니다.
- 그 이후 전송 메세지에는 `up 이후 N분`을 포함합니다.

## 실행

`--help` 확인 방법과 주요 명령은 [help.md](help.md)를 참고하세요.

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/tinyGW/pulsedav
streamlit run app.py

수동 1회 전송:
python3 sender.py --once
python3 sender.py --once --print-crontab --config this_config.conf
```

설정 파일 경로를 직접 지정하려면:

```bash
python3 sender.py --once --config /path/to/custom-settings.json
```

반복 전송:

```bash
python3 sender.py --loop
```

반복 전송에서도 설정 파일 경로를 지정할 수 있습니다:

```bash
python3 sender.py --loop --config /path/to/custom-settings.json
```

crontab 에 넣을 예시 라인을 CLI 에서 바로 출력하려면:

```bash
python3 sender.py --print-crontab
python3 sender.py --print-crontab --config /path/to/custom-settings.json
```

ipTIME ping 상태와 LAN 장치 목록을 WebDAV로 먼저 전송한 뒤 일반 PulseDAV 정보도 이어서 전송하려면:

```bash
python3 sender.py --iptime-list
python3 sender.py --iptime-list --config /path/to/custom-settings.json
```

## 설정 파일

최신 `settings.json` 구조를 기준으로 개인 설정 파일을 생성하거나 갱신하려면:

```bash
python3 update_settings.py
# 파일명이 다르거나 다른 경로에 있는 경우
python3 update_settings.py --template setting.json --config this_setting.json
```

기본 출력은 스크립트와 같은 폴더의 `this_settings.json`입니다. 기존 파일의
WebDAV ID/비밀번호, ipTIME ID/비밀번호 및 같은 항목의 사용자 설정을 유지하고,
새 항목은 템플릿 값으로 추가하며 템플릿에서 삭제된 항목은 제거합니다.
템플릿 자체는 수정하지 않습니다. 기존 출력 파일이 없으면 템플릿을 복사하므로
사용 전에 접속 정보를 수정해야 합니다.

인증 항목이 삭제/이동되었거나 기존 값의 자료형이 달라졌다면 자동으로 추측하지 않고
오류로 중단합니다. 이때 원본은 변경되지 않으며 항목을 직접 맞춘 뒤 재실행합니다.
`webdav.sub`은 문자열과 문자열 배열을 모두 지원하므로 기존 배열도 보존합니다.
출력 파일과 덮어쓰기 전 생성하는 `this_settings.json.bak.*` 백업은 소유자만 읽고
쓸 수 있는 권한(`0600`)으로 저장됩니다. 인증 정보는 화면에 출력하지 않습니다.

- 기본 설정 파일은 `/Users/tinyos/devel_opment/BerePi/apps/tinyGW/pulsedav/settings.json` 입니다.
- CLI 에서 `--config` 를 주면 해당 JSON 파일을 설정 파일로 사용합니다.
- 지정한 설정 파일이 없으면 기본값 템플릿과 병합되어 동작합니다.
- 여러 서브 디렉토리에 동시에 저장하려면 `"webdav": { "sub": ["office", "backup"] }` 처럼 JSON 배열을 사용합니다. Streamlit 화면에서는 서브 디렉토리를 한 줄에 하나씩 입력하면 배열로 저장됩니다.
- `--print-crontab` 은 현재 설정 기준으로 `@reboot` 와 주기 실행 cron 라인을 출력합니다.
- `--config` 와 함께 쓰면 해당 설정 파일 경로가 포함된 cron 라인을 출력합니다.
- cron 예시의 실행 시각은 `pulsedav.log` 첫 줄에 기록됩니다.
- `@reboot` 실행은 `pulsedav.log` 와 전송 Markdown 상태 메시지에 `reboot 시점` 문구를 남깁니다.
- cron 예시의 로그 리다이렉션은 `>` 를 사용하므로, `pulsedav.log` 가 매 실행마다 새로 써져서 무한정 커지지 않습니다.
- ipTIME 설정은 기본적으로 `../list_ip/setting.conf` 를 읽습니다. JSON 설정의 `iptime.config_path`, `iptime.router_ip`, `iptime.user_id`, `iptime.user_pw`, `iptime.timeout_seconds` 값으로 직접 지정할 수도 있습니다.
- `iptime.user_id` 또는 `iptime.user_pw` 가 비어 있으면 ipTIME ping/API 호출을 실행하지 않습니다.

## 부팅 자동 전송 예시

```cron
@reboot cd /Users/tinyos/devel_opment/BerePi/apps/tinyGW/pulsedav && { echo 'reboot 시점'; /usr/bin/python3 -c 'from datetime import datetime; from time_utils import SEOUL; d=datetime.now(SEOUL); print(f"{d.year:04d}-{d.month:02d}-{d.day:02d} {d.hour:02d}:{d.minute:02d}:{d.second:02d} {d.tzname()}")'; /usr/bin/python3 sender.py --once --reboot; } > pulsedav.log 2>&1
*/30 * * * * cd /Users/tinyos/devel_opment/BerePi/apps/tinyGW/pulsedav && { /usr/bin/python3 -c 'from datetime import datetime; from time_utils import SEOUL; d=datetime.now(SEOUL); print(f"{d.year:04d}-{d.month:02d}-{d.day:02d} {d.hour:02d}:{d.minute:02d}:{d.second:02d} {d.tzname()}")'; /usr/bin/python3 sender.py --once; } > pulsedav.log 2>&1
```

## 게이트웨이 감시 및 자동 재부팅 (Linux)

`--gateway-watchdog`는 WebDAV 전송과 별도로 기본 IPv4 게이트웨이를 자동 조회하고 ping을 보냅니다.
여러 기본 경로가 있으면 metric이 가장 낮은 경로를 선택합니다. 실패하면 6분 간격으로 현재
게이트웨이를 다시 조회·점검하며, **첫 실패부터 30분 이상 연속 실패**한 경우에만 재부팅합니다.
한 번이라도 응답하면 실패 시간을 초기화하고 해당 점검을 종료합니다. 기본 경로 자체가 없는
상태도 접속 실패에 포함합니다. `ip`/`ping` 실행 오류는 로그를 남기고 종료하며 재부팅하지 않습니다.

```bash
cd ~/devel/BerePi/apps/tinyGW/pulsedav
# 실제 재부팅 없이 점검 (실패 시 최대 30분 대기)
python3 sender.py --gateway-watchdog --gateway-dry-run
# 30분 연속 실패 시 실제 재부팅하는 1회 점검
sudo python3 sender.py --gateway-watchdog
# 부팅 직후 + 매시 정각 자동 점검 등록 (root crontab)
sudo python3 sender.py --gateway-watchdog --install-crontab
# 등록할 내용만 보기
python3 sender.py --gateway-watchdog --print-crontab
```

자동 등록은 `@reboot`와 `0 * * * *` 두 항목입니다. 부팅 직후 게이트웨이를 얻어 바로 점검하고,
이후 시스템 현지 시각의 매시 정각에 점검합니다. 예: 10:00 첫 실패 → 10:06, 10:12, 10:18,
10:24, 10:30 재확인 → 10:30에도 실패하면 재부팅. 정각 사이에 발생한 장애는 다음 정각에 처음 감지됩니다.
프로세스 잠금으로 중복 점검을 방지합니다. 점검 프로세스가 중단되면 다음 실행에서 실패 시간을
새로 측정합니다. Linux의 `iproute2`, `iputils-ping`, cron 및 `reboot` 명령이 필요합니다.
실제 재부팅 모드는 root 권한이 필요하고, 게이트웨이가 ICMP ping에 응답하도록 설정되어 있어야 합니다.
로그는 `gateway-watchdog.log`이며 실행할 때마다 덮어씁니다. WebDAV 전송 작업은 별도로 유지됩니다.

### crontab 중복 없이 등록·갱신

```bash
# 기존 상태 전송 등록도 같은 명령으로 갱신 가능
python3 sender.py --install-crontab --config /path/to/this_settings.json --interval-minutes 30
crontab -l
sudo crontab -l
```

`--install-crontab`은 현재 사용자의 crontab에서 **현재 앱 경로의 같은 종류 작업**을 모두 제거한 뒤
최신 설정의 부팅용·주기용 항목을 각각 하나씩 등록합니다. 과거에 수동으로 복사한 `cd 앱경로 && ... sender.py`
형식도 교체합니다. 게이트웨이 감시와 상태 전송은 별개 종류로 유지하고, 다른 작업과 주석·환경변수는 보존합니다.
등록 전 전체 crontab은 앱 폴더의 `crontab-backup-*.txt`에 백업합니다. root와 일반 사용자 crontab은
서로 다르므로 등록에 사용한 동일 계정으로 갱신하세요. 다른 설치 경로의 작업은 자동 삭제하지 않습니다.
감시를 해제하려면 `sudo crontab -e`에서 `sender.py --gateway-watchdog`가 들어간 두 줄을 제거합니다.
이미 실행 중인 점검은 별도로 종료해야 합니다.

## 로그인 시 crontab 확인

`check_login_pulsedav.sh` 는 사용자 crontab 또는 비밀번호 없이 확인 가능한 root crontab 에 PulseDAV 실행 라인이 있으면 아무 것도 출력하지 않습니다. 실행 라인이 없으면 로그인 시 확인할 수 있도록 `Missing PulseDAV` 를 출력합니다.

```bash
/Users/tinyos/devel_opment/BerePi/apps/tinyGW/pulsedav/check_login_pulsedav.sh
```

로그인할 때마다 확인하려면 `~/.bashrc`, `~/.bash_profile`, `~/.profile`, `~/.zshrc` 중 실제 로그인 셸이 읽는 파일에 아래 라인을 추가합니다.

```bash
[ -x /Users/tinyos/devel_opment/BerePi/apps/tinyGW/pulsedav/check_login_pulsedav.sh ] && /Users/tinyos/devel_opment/BerePi/apps/tinyGW/pulsedav/check_login_pulsedav.sh
```


## WebDAV 기록 상태 점검

`--check-status`는 현재 머신의 설정된 `/tinyGW/<sub>/<호스트명>` 경로만 확인합니다.
`sub`가 여러 개면 현재 머신의 모든 설정된 업로드 경로를 확인합니다.
`--check-status-all`은 `/tinyGW` 전체 노드를 확인합니다.
두 모드 모두 대상 경로 하위를 WebDAV `PROPFIND Depth: 1`로 반복 탐색합니다.
모든 파일의 수정 시각을 서울 시간 ISO 8601 (`+09:00`)로 저장하며, 최신 PulseDAV Markdown을 WebDAV GET으로
읽어 호스트명, 내부/Public IP, 설정된 SSH 포트를 추출합니다. 인증은 기존 설정 파일을 사용합니다.
점검은 원격 파일을 업로드하거나 삭제하지 않으며 로컬 전송 state도 변경하지 않습니다.

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/tinyGW/pulsedav
python3 pulsedav.py --check-status
# cron을 조회할 수 없거나 설정이 여러 개이면 명시적으로 지정
python3 pulsedav.py --check-status --config this_settings.json
# 모든 노드 확인
python3 pulsedav.py --check-status-all --config this_settings.json
# sender.py에서도 같은 인자를 지원
python3 sender.py --check-status --config this_settings.json --max-age-minutes 90
```

설정 자동 탐색은 사용자 crontab과 비밀번호 없이 조회 가능한 root crontab의 `cd`,
`sender.py`/`pulsedav.py`, `--config`를 해석합니다. shell 변수 등 해석할 수 없는 설정은
`--config`로 지정하세요. cron 원문과 비밀번호는 출력 파일에 기록하지 않습니다.
현재 실행 환경에서 cron을 읽지 못하는 경우에도 명시적 설정으로 점검할 수 있습니다.

기본 출력은 workspace의 `workshot/server_list/server_status.json` 및
`server_status.txt`입니다. `--status-output-dir /path/to/output`으로 변경할 수 있습니다.
Tree에는 모든 폴더와 파일 시각이 표시되며 전체 점검의 Markdown 파일은 최신 한 개와 개수로 요약됩니다. JSON에는 전체 파일 목록, 서버별 최신 파일,
최근 PulseDAV 기록, 누락/실패 정보가 포함됩니다.

전체 점검의 서버 디렉터리는 `pulse_*.md`가 있는 디렉터리와 현재 설정의 업로드 대상에서 찾습니다.
로컬 점검은 현재 호스트명의 설정된 업로드 대상만 조회하며 다른 노드는 탐색하지 않습니다.
`--server-list`는 로컬 점검에서 해당 경로의 메타데이터만 보완하고 점검 범위를 늘리지 않습니다.
JSON의 `scope`와 `target_directories`에서 실제 점검 범위를 확인할 수 있습니다.
두 모드는 동일한 결과 파일을 갱신하므로 별도로 보관하려면 `--status-output-dir`을 지정하세요.
아직 기록이 없거나 별도의 디렉터리 구조를 사용하는 서버는 `--server-list inventory.json`으로
추가하세요. 목록의 필드는 보고서에서 추출한 메타데이터보다 우선합니다.

```json
{
  "servers": [
    {
      "server_name": "gateway-1",
      "ip_address": "192.0.2.10",
      "open_port": 22,
      "directory": "tinyGW/site/gateway-1"
    }
  ]
}
```

`latest_file`은 서버 디렉터리 하위 모든 파일 중 최신 파일입니다. `status`는
`pulse_*.md`의 수정 시각을 기준으로 판단하므로 다른 파일 갱신이 기록 중단을 숨기지 않습니다.
기본 지연 기준은 선택한 설정의 `schedule.interval_minutes`의 2배이며 모든 서버에 적용됩니다.
서버마다 전송 주기가 다르면 `--max-age-minutes`로 적절한 기준을 지정하세요.
`ok`는 최근 기록 존재, `stale`은 지연, `missing`은 기록 없음,
`unknown`은 조회 실패, `clock_skew`는 미래 시각입니다.
이는 최근 기록 존재 여부이며 다음 전송 성공이나 SSH 포트의 실제 개방 여부를 보장하지 않습니다.
`open_port`는 보고서 또는 목록에 명시된 포트입니다. 추출 불가 항목은 JSON null입니다.

일부 디렉터리가 실패해도 다른 디렉터리를 계속 검사하고 `scan_complete: false`와 오류를 저장합니다.
종료 코드는 정상 0, 지연/누락/시각 이상 1, 설정 오류/불완전 조회 2입니다.
설정 오류는 원격 점검 전에 종료되므로 기존 출력 파일을 갱신하지 않습니다.

검증:

```bash
python3 -m unittest discover -s . -p test_status_check.py -v
```

## Docker 상태 수집 권한

`permission denied ... /var/run/docker.sock`는 PulseDAV 실행 계정이 Docker 소켓에
접근할 수 없다는 뜻입니다. 컨테이너가 중단되었다는 뜻은 아닙니다.
보고서에는 권한 부족을 표시하며 PulseDAV가 자동으로 sudo를 실행하거나 권한을 변경하지 않습니다.

해당 머신에서 cron 실행 계정과 동일한 계정으로 확인하세요.

```bash
id
ls -l /var/run/docker.sock
docker ps
```

Linux Docker Engine의 소켓 그룹이 `docker`라면, 해당 계정에 Docker 관리 권한을
부여하기로 한 경우 아래처럼 그룹에 추가할 수 있습니다. `USER`는 PulseDAV 실행 계정이어야 합니다.

```bash
sudo usermod -aG docker "$USER"
```

로그아웃 후 다시 로그인하고 `docker ps`를 확인하세요. Docker 그룹은 root 수준의
권한을 부여합니다. Rootless Docker나 Docker Desktop 환경은 해당 계정의 Docker context와
소켓 경로를 확인하세요.
참고: https://docs.docker.com/engine/install/linux-postinstall/


### 실행 시 Docker 그룹 경고

`python3 sender.py ...` 또는 `python3 pulsedav.py ...` 실행 시 Linux에서는 현재
실행 계정의 `docker` 그룹을 확인합니다. `--once`, `--loop`, `--check-status`,
`--check-status-all` 등에서 시작할 때 한 번 검사하며, 경고가 있어도 실행을 계속합니다.
경고는 stderr로 출력되어 `2>&1`로 저장하는 cron 로그에도 포함됩니다.

```text
WARNING: 현재 사용자 'tinyos'이 docker 그룹에 포함되어 있지 않습니다. Docker 소켓 접근 시 permission denied가 발생할 수 있습니다.
Docker 관리 권한을 부여하려면: sudo usermod -aG docker tinyos
그룹 변경 후 로그아웃/로그인하세요. docker 그룹은 root 수준의 권한을 부여합니다.
```

- 현재 프로세스의 기본/보조 그룹에 `docker`가 있으면 경고하지 않습니다.
- 계정에 그룹을 추가했어도 실행 중인 프로세스에 적용되지 않았으면 재로그인을 안내합니다.
- `docker` 그룹 자체가 없으면 Docker 설치 및 context/소켓 설정 확인을 안내합니다.
- root 및 macOS/Windows는 이 Linux 그룹 검사를 생략합니다.
- `$USER` 대신 실제 프로세스의 실행 UID로 계정을 확인합니다. cron 실행 계정에도 적용됩니다.

Rootless Docker 또는 원격 Docker context는 `docker` 그룹 없이도 정상 동작할 수 있습니다.
따라서 그룹 경고는 컨테이너 장애를 의미하지 않으며, 실제 조회 성공 여부는 보고서의
Docker 운영 상태에서 확인하세요. 프로그램은 그룹 가입이나 소켓 권한 변경을 자동 실행하지 않습니다.


## 시간 표시

보고서 생성 시각, 상태 점검의 파일 수정 시각과 점검 시각, 전송 상태의 `last_sent_at`,
재부팅·게이트웨이 로그와 새 보고서 파일명의 날짜는 서버 OS의 시간대와 관계없이
서울 시간(`Asia/Seoul`)을 사용합니다. 텍스트에는 `KST`, JSON의 ISO 8601 시각에는
`+09:00`이 표시됩니다. 예: `2026-09-26T13:00:00+09:00`.
WebDAV가 UTC로 반환한 시각도 서울 시간으로 변환하며 기록의 경과 시간 계산은 유지합니다.
기존 보고서와 파일명은 변경하지 않습니다.

새로 생성하는 cron 예시도 서울 시간으로 로그를 출력합니다. 이미 등록된 cron 명령의
시각 출력 코드는 자동으로 바뀌지 않으므로 `--print-crontab`으로 확인 후 반영하세요.
cron 실행 스케줄 자체는 머신의 cron 시간대 설정을 따릅니다.


### 전체 상태 점검의 Markdown 파일 요약

```bash
python3 sender.py --config ./this_settings.json --check-status-all
```

전체 점검의 콘솔 tree와 `server_status.txt`는 각 디렉터리의 `.md` 파일을
수정 시각 기준 최신 한 개와 전체 개수로 요약합니다. 하위 디렉터리는 각각 집계하고,
Markdown 이외의 파일은 그대로 표시합니다.

```text
└── iMac27WS/
    └── pulse_20260926_140000.md  2026-09-26T14:00:00+09:00 [MD 총 48개, 최신 1개 표시]
```

모든 파일의 수정 시각을 조회하며 JSON의 전체 파일 목록은 유지합니다.
수정 시각을 확인하지 못한 파일이 있으면 미확인 개수를 함께 표시합니다.
`--check-status`의 로컬 점검 tree는 기존처럼 모든 파일을 표시합니다.

## 디스크 용량 예측

용량 표시·이력 기록·예측·Telegram 자동 경고 및 수동 테스트는 **전체 용량 100GB 이상**인
파일시스템만 대상으로 합니다. `df`가 반환하는 전체 용량 기준이며,
100GB는 100,000,000,000바이트입니다. 작은 부팅 파티션 등은 제외됩니다.

HDD 공간 항목을 켜면 파일시스템별 사용률이 **80% 이상**일 때
`disk_history.json`에 측정 시각과 사용량을 자동 기록합니다. **90% 이상(잔여 10% 이하)**이면
현재 사용률·잔여 용량, 관측 기간, 평균 증가량(GiB/일), 100% 도달까지 남은 일수와
예상 날짜(KST)를 WebDAV 및 Telegram 보고서에 표시합니다.

평균 증가량은 저장된 최초 측정부터 현재까지의 순증가량을 경과 일수로 나눈 값이며,
예상 남은 일수는 현재 사용 가능 공간을 평균 증가량으로 나눠 계산합니다.
예약 블록을 제외한 `df`의 사용 가능 용량을 기준으로 합니다. 증가 속도가 계속 같다는
가정의 추정치이며, 이력이 부족하거나 사용량이 늘지 않으면 사유를 표시합니다.
최대 최근 10,000개 측정값을 디스크별로 보관하며, 사용률이 80% 미만이 되거나
용량이 변경되면 관측 기간을 다시 시작합니다. 이력 파일은 Git에 포함하지 않습니다.

## Telegram 동시 전송 (선택)

### 현재 디스크 용량 테스트 전송

PulseDAV 앱 디렉터리에서 실행합니다. Telegram 수신 설정은 먼저
`telegram-send --configure`로 완료하세요.

```bash
python3 sender.py --test-telegram-disk --config this_settings.json
```

기본 `settings.json`을 사용한다면 `--config this_settings.json`은 생략합니다.
`python3 pulsedav.py --test-telegram-disk --config this_settings.json`으로도 실행할 수 있습니다.
현재 100GB 이상 디스크 용량, 파일시스템 이름·사용률과 기존 이력에 따른 용량 예측을
호스트명·내부 IP·공인 IP와 함께 **Telegram 문자 메시지로 전송**합니다.
`disk_test.md` 파일은 생성하거나 첨부하지 않습니다.
수동 테스트이므로 사용률 95% 초과 여부, HDD 공간 포함 설정, `telegram.enabled` 값과
관계없이 1회 전송합니다. 설정 파일의 Telegram 실행 파일·수신 설정 경로·제한 시간은
그대로 사용하며, 저장된 설정은 변경하지 않습니다.
WebDAV에는 저장하지 않고, 디스크 이력과 하루 2회 자동 경고 전송 기록도 변경하지 않습니다.
콘솔에도 현재 용량과 전송 결과를 표시하며 성공 시 종료 코드 0, 실패 시 1을 반환합니다.

모든 Telegram 첨부 파일의 캡션에 전송 장비 정보를 함께 표시합니다.

```text
🖥️ Host: gateway-host
🏠 Local IP: 192.168.1.2
🌐 Public IP: 203.0.113.1
💽 /dev/sda1 (/): 96%
```

100GB 이상 파일시스템의 이름·마운트 경로·사용률을 캡션 문자에 함께 표시합니다.
디스크가 많아 캡션 길이 제한을 넘으면 전체 목록을 첨부 파일에 포함합니다.

시스템 보고서와 디스크 경고는 수집한 정보를 재사용하며, ipTIME 보고서는 전송 시 조회합니다.

디스크 사용률이 **95% 초과**이고 HDD 공간 항목 및 `telegram.enabled`가 켜져 있으면,
용량과 예상 포화일을 담은 별도 `disk_alert.md` 경고도 전송합니다.
한국 시간 기준 오전(00:00~11:59)·오후(12:00~23:59) 각각 최초 점검 시 한 번씩,
하루 최대 2회 전송합니다. 여러 디스크의 경고는 한 파일에 모읍니다.
`--loop` 또는 정기 cron 실행이 필요하며, 점검 실행이 없는 시간대의 경고는 소급하지 않습니다.
WebDAV 저장 전에 경고를 시도하므로 WebDAV 장애가 있어도 전송할 수 있습니다.
성공한 전송 구간은 `disk_alert_state.json`에 저장해 재시작·중복 실행 시에도 중복을 막고,
전송 실패 시 다음 점검에서 재시도합니다. 95% 이하면 별도 Telegram 경고를 보내지 않습니다.
기존 정기 Telegram 보고서 전송은 유지되므로 하루 2회 제한은 별도 디스크 경고에 적용됩니다.

WebDAV 저장에 성공한 보고서를 `telegram-send --file`로 Telegram에도 전송할 수 있습니다.
시스템 보고서와 `--iptime-list` 보고서 모두 적용되며, WebDAV 저장 대상이 여러 곳이어도
Telegram에는 보고서별로 한 번만 전송합니다. 긴 보고서와 표를 보존하기 위해 Markdown
파일을 첨부합니다. WebDAV 저장 후 순서대로 전송하며, Telegram 실패·시간 초과는 경고로
출력하고 WebDAV 저장 결과와 전송 상태 기록은 유지합니다. WebDAV 저장이 실패하면
일반 보고서의 Telegram 전송은 실행하지 않습니다. 단, 사용률 **95% 초과 디스크 경고**는
WebDAV 저장 성공·실패와 관계없이 앞서 설명한 하루 최대 2회 기준으로 전송합니다.
상태 점검과 게이트웨이 감시에는 적용되지 않습니다.

먼저 실행 계정에서 설치하고 수신 대상을 설정합니다.

```bash
pipx install telegram-send
telegram-send --configure
```

### `telegram-send --configure` 설정 방법

개인 Telegram 계정으로 받는 경우 다음 순서로 설정합니다. PulseDAV 또는 cron을
실행할 동일한 OS 계정의 터미널에서 진행하세요.

1. Telegram에서 공식 [@BotFather](https://t.me/BotFather) 대화를 열고 `/newbot`을 보냅니다.
2. 안내에 따라 봇의 표시 이름과 사용자 이름을 지정합니다. 사용자 이름은 `bot`으로
   끝나야 합니다. 발급된 **봇 토큰**을 복사합니다.
3. 터미널에서 `telegram-send --configure`를 실행하고 토큰 입력 요청에 붙여넣은 뒤
   Enter를 누릅니다.
4. 터미널에 표시되는 봇 링크를 Telegram에서 열고 **시작(Start)**을 누릅니다.
   이어서 터미널에 표시된 인증 숫자를 **해당 봇과의 대화에** 메시지로 보냅니다.
   이 숫자는 봇 토큰이나 Telegram 로그인 인증번호가 아닙니다.
5. 터미널과 Telegram에 설정 완료 안내가 나타나는지 확인합니다. 설정 파일은
   자동으로 저장되므로 매번 `--configure`를 실행할 필요가 없습니다.
6. 아래 명령으로 메시지와 파일 수신을 확인합니다. 파일 전송 명령은 PulseDAV 앱
   디렉터리에서 실행합니다.

```bash
telegram-send "PulseDAV Telegram 연결 테스트"
telegram-send --file README.md
```

별도 설정 파일을 사용하려면 처음부터 경로를 지정하고, 테스트에도 같은 경로를 사용합니다.

```bash
telegram-send --config "$HOME/.config/pulsedav/telegram.conf" --configure
telegram-send --config "$HOME/.config/pulsedav/telegram.conf" "PulseDAV Telegram 연결 테스트"
```

이 경우 PulseDAV의 `telegram.config_path`에 `~/.config/pulsedav/telegram.conf`를
지정합니다. 봇 토큰이 들어 있는 설정 파일은 Git에 커밋하지 마세요.
명령을 찾지 못하면 `pipx ensurepath` 실행 후 터미널을 다시 열고 확인합니다.
인증 숫자를 보냈는데 설정이 끝나지 않으면 BotFather가 아니라 새로 만든 봇에
정확한 숫자를 보냈는지 확인하세요.

그룹으로 받으려면 `telegram-send --configure-group`을 실행하고, 안내되는 봇을 그룹에
추가한 뒤 터미널에 표시된 인증 메시지를 그룹에 보냅니다. 채널로 받으려면
`telegram-send --configure-channel`을 사용하며 봇을 채널 관리자로 추가해야 합니다.
별도 설정 경로는 두 명령에도 `--config`로 지정할 수 있습니다.

### PulseDAV 설정

설정 파일의 `telegram` 항목을 다음과 같이 지정합니다. 기본값은 **꺼짐**입니다.

```json
"telegram": {
  "enabled": true,
  "executable": "telegram-send",
  "config_path": "",
  "timeout_seconds": 60
}
```

- `enabled`: `true`이면 전송, `false`이면 WebDAV에만 저장합니다.
- `executable`: 실행 파일 이름 또는 절대 경로입니다. cron에서 PATH가 다르면 `/home/user/.local/bin/telegram-send`처럼 지정합니다. 명령 옵션은 이 값에 넣지 않습니다.
- `config_path`: 빈 문자열이면 telegram-send의 기본 설정을 사용합니다. 별도 설정 파일은 절대 경로 또는 PulseDAV 앱 디렉터리 기준 상대 경로로 지정합니다. `~`도 지원합니다.
- `timeout_seconds`: Telegram 명령의 최대 실행 시간(양의 정수, 초)입니다.

별도 수신 설정은 `telegram-send --config /path/to/telegram.conf --configure`로 만듭니다.
cron에서도 해당 설정을 읽을 수 있는 동일한 계정을 사용하세요. 웹 설정 화면의
**Telegram 전송**에서도 켜기/끄기, 실행 파일, 설정 파일, 제한 시간을 변경할 수 있습니다.

기존 개인 설정 파일을 쓰는 경우 해당 파일에 `telegram` 항목을 추가하거나
`python3 update_settings.py --config /path/to/this_settings.json`으로 최신 항목을 반영합니다.
이후 평소처럼 `python3 sender.py --once --config /path/to/this_settings.json`을 실행합니다.
`--loop`는 시작 시 읽은 설정을 사용하므로 변경 후 프로세스를 재시작해야 합니다.
보고서 전송 함수의 반환값에는 `telegram.status` (`disabled`, `sent`, `failed`)가 포함됩니다.
임시 첨부 파일은 성공·실패 후 삭제됩니다.

설치와 CLI 옵션 참고: [telegram-send 공식 문서](https://github.com/rahiel/telegram-send).

## WebDAV /tinyGW 전체 보고서 집계·저장·Telegram 전송

실행 시 콘솔에 한국 시간(KST)과 시작 이후 경과 초를 표시합니다.
설정 검증, 디렉터리 조회, Markdown 읽기·처리 건수, 집계 호스트 수,
로그 저장, Telegram 메시지별 전송 시작·완료 및 전체 종료 상태를 출력합니다.
전체 파일 수는 탐색하면서 발견하므로 WebDAV 진행률은 처리 건수로 표시합니다.
WebDAV의 표준 호스트별 폴더에서는 `pulse_YYYYMMDD_HHMMSS.md` 중 최신 정상 보고서만
다운로드합니다. 최신 파일을 읽지 못하면 이전 파일을 확인하며, 오래된 보고서의 반복 다운로드를 줄입니다.
WebDAV에서 ipTIME·LLM 상태 등 다른 종류의 Markdown은 다운로드하지 않습니다.
진행 출력은 표준 오류(stderr)에 즉시 기록하며 집계 파일·Telegram 본문에는 포함하지 않습니다.
저장 시작 시 output 디렉터리를, 저장 완료 시 생성된 output 파일의 절대 경로를 표시합니다.

```text
[2026-10-13 10:00:00 KST | 경과 0.0초] tinyGW 집계 시작
[2026-10-13 10:00:02 KST | 경과 2.1초] Markdown 처리 완료 #1 (집계 호스트 1개)
[2026-10-13 10:00:05 KST | 경과 5.3초] 전체 작업 완료
```

설정 파일 경로는 정확한 파일명을 사용하세요. 예를 들어 `this.setting.json`과
`this_settings.json`은 서로 다른 파일입니다. 파일이 없거나 JSON 형식이 잘못되면
접속 전에 중단하며, 실제 사용한 설정 경로를 콘솔에 표시합니다.
HTTP 401은 인증 정보, 403은 읽기 권한, 404는 WebDAV root와 `/tinyGW` 경로를
확인하세요. HTTP 405는 일반 웹 주소 대신 PROPFIND를 지원하는 WebDAV 주소인지 확인합니다.
`dns_error`는 서버 호스트명을 해석할 수 없다는 의미입니다. `webdav.hostname`의 도메인
오타·DDNS 등록 상태와 실행 장비의 DNS/VPN 연결을 확인하세요. 이 오류는 인증 전 단계입니다.

`check_tinyGW_all.py`는 PulseDAV 설정의 WebDAV 서버에서 `/tinyGW` 하위 Markdown을
재귀적으로 읽습니다. 호스트별 최신 시스템 보고서의 내부 IP·호스트명·최근 전송 시각과
100GB 이상 파일시스템의 이름·마운트 경로·빈 공간%를 집계합니다.
`webdav.sub`에 관계없이 전체 `/tinyGW`를 조회하며, 설정의 WebDAV root를 기준으로 합니다.

PulseDAV 앱 디렉터리에서 실행하세요.

```bash
# WebDAV에서 읽고 logs에 집계 파일 저장
python3 check_tinyGW_all.py --config this_settings.json

# 저장된 집계 파일의 내용을 Telegram 문자로 전송
python3 check_tinyGW_all.py --config this_settings.json --send

# 별도 Telegram 수신 설정 사용
python3 check_tinyGW_all.py --config this_settings.json --send \
  --telegram-config ~/.config/pulsedav/telegram.conf
```

기본 설정은 앱의 `settings.json`입니다. WebDAV 계정은 `/tinyGW` 목록·파일 읽기 권한이
필요합니다. Telegram은 실행 계정에서 `telegram-send --configure`로 먼저 설정하세요.
실행 파일·수신 설정 파일·제한 시간은 PulseDAV `telegram` 설정을 사용하며
`--executable`, `--telegram-config`, `--timeout`으로 재정의할 수 있습니다.
`--send`는 명시적 수동 전송이므로 `telegram.enabled`와 관계없이 전송합니다.

집계 결과는 기본적으로 `BerePi/apps/tinyGW/pulsedav/logs/` 아래
`tinyGW_all_YYYYMMDD_HHMMSS_마이크로초.txt`에 UTF-8로 저장합니다.
`--logs-dir /path/to/logs`로 저장 위치를 바꿀 수 있습니다.
파일 저장을 완료한 뒤 해당 파일 내용을 다시 읽어 Telegram으로 전송하며 첨부는 없습니다.
전송 실패 시에도 파일은 남으며, 긴 내용은 여러 문자 메시지로 나눕니다.

기존 로컬 파일 집계는 `--root /srv/webdav/tinyGW`로 선택할 수 있습니다.
같은 호스트의 중복 보고서는 한 번만 포함하며 ipTIME 등 시스템 보고서가 아닌 파일은 제외합니다.
최근 전송 시각은 보고서 생성 시각입니다. 없으면 보고서 파일명, 그마저 없으면
WebDAV 수정 시각(로컬 모드는 파일 수정 시각)을 사용합니다.
빈 공간%는 `100 - 사용률`로 계산하며 최신 보고서에 용량 정보가 없으면 정보 없음으로 표시합니다.
원본 파일은 변경하지 않습니다. 파일 읽기 실패는 콘솔과 집계 파일에 건수로 표시하며,
디렉터리 조회 실패·집계할 보고서 없음·저장 또는 전송 실패 시 종료 코드 1을 반환합니다.

### 집계 호스트 정렬 및 개수 제한

로그와 Telegram 본문은 최근 전송 시각이 최신인 호스트부터 정렬합니다.
시각 정보가 없으면 마지막에 표시하며, 동일 시각은 호스트명 순서로 정렬합니다.
`--limit N`으로 최신 N개 호스트만 로그에 저장하고 전송합니다.
생략하면 전체, 전체 호스트 수보다 크면 존재하는 호스트만 포함합니다.
N은 양의 정수이며, 최신 순서를 판단하기 위한 집계는 전체 호스트를 대상으로 합니다.

```bash
python3 check_tinyGW_all.py --config this.setting.json --limit 5 --send
```
