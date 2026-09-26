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

`--check-status`는 `/tinyGW` 전체를 WebDAV `PROPFIND Depth: 1`로 반복 탐색합니다.
모든 파일의 수정 시각을 UTC ISO 8601로 저장하며, 최신 PulseDAV Markdown을 WebDAV GET으로
읽어 호스트명, 내부/Public IP, 설정된 SSH 포트를 추출합니다. 인증은 기존 설정 파일을 사용합니다.
점검은 원격 파일을 업로드하거나 삭제하지 않으며 로컬 전송 state도 변경하지 않습니다.

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/tinyGW/pulsedav
python3 pulsedav.py --check-status
# cron을 조회할 수 없거나 설정이 여러 개이면 명시적으로 지정
python3 pulsedav.py --check-status --config this_settings.json
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

서버 디렉터리는 `pulse_*.md`가 있는 디렉터리와 현재 설정의 업로드 대상에서 찾습니다.
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
