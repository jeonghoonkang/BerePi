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
- 36개월보다 오래된 원격 파일은 자동 삭제합니다.
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

기본 출력은 workspace의 `workshot/2remember/server_list/server_status.json` 및
`server_status.txt`입니다. `--status-output-dir /path/to/output`으로 변경할 수 있습니다.
Tree에는 모든 폴더와 파일 시각이 표시되고 JSON에는 파일 목록, 서버별 최신 파일,
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
