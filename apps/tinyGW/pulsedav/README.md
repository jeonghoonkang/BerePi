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
@reboot cd /Users/tinyos/devel_opment/BerePi/apps/tinyGW/pulsedav && { echo 'reboot 시점'; /usr/bin/python3 -c 'from datetime import datetime; d=datetime.now().astimezone(); print(f"{d.year:04d}-{d.month:02d}-{d.day:02d} {d.hour:02d}:{d.minute:02d}:{d.second:02d} {d.tzname()}")'; /usr/bin/python3 sender.py --once --reboot; } > pulsedav.log 2>&1
*/30 * * * * cd /Users/tinyos/devel_opment/BerePi/apps/tinyGW/pulsedav && { /usr/bin/python3 -c 'from datetime import datetime; d=datetime.now().astimezone(); print(f"{d.year:04d}-{d.month:02d}-{d.day:02d} {d.hour:02d}:{d.minute:02d}:{d.second:02d} {d.tzname()}")'; /usr/bin/python3 sender.py --once; } > pulsedav.log 2>&1
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
