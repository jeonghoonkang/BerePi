# PulseDAV 실행 도움말

## `--help` 확인하기

터미널에서 PulseDAV 디렉터리로 이동한 뒤 실행합니다.

```bash
cd ~/devel_opment/BerePi/apps/tinyGW/pulsedav
python3 sender.py --help
```

짧은 옵션인 `-h`도 같은 도움말을 출력합니다.

```bash
python3 sender.py -h
```

`pulsedav.py`로도 동일하게 사용할 수 있습니다.

```bash
python3 pulsedav.py --help
```

다른 디렉터리에서는 전체 경로를 지정하세요.

```bash
python3 ~/devel_opment/BerePi/apps/tinyGW/pulsedav/sender.py --help
```

`--help`는 사용 가능한 옵션을 출력하고 종료합니다. 설정 파일이나 WebDAV 접속이
필요하지 않으며, 보고서를 전송하거나 cron을 등록하지 않습니다.

## 자주 사용하는 명령

아래 명령은 PulseDAV 디렉터리에서 실행합니다. `this_settings.json`은 예시이므로
실제 설정 파일명에 맞추세요. `this.settings.json`과는 다른 이름입니다.

```bash
# 보고서 한 번 전송
python3 sender.py --config ./this_settings.json --once

# 현재 머신의 WebDAV 기록 상태만 확인
python3 sender.py --config ./this_settings.json --check-status

# /tinyGW 아래 모든 노드의 WebDAV 기록 상태 확인
python3 sender.py --config ./this_settings.json --check-status-all

# 현재 머신의 기록이 90분 이내에 갱신됐는지 확인
python3 sender.py --config ./this_settings.json --check-status --max-age-minutes 90

# 설정된 주기로 계속 전송 (종료: Ctrl+C)
python3 sender.py --config ./this_settings.json --loop

# 등록할 cron 명령을 출력해서 확인
python3 sender.py --config ./this_settings.json --print-crontab
```

## 주요 옵션

| 옵션 | 설명 |
| --- | --- |
| `-h`, `--help` | 도움말을 출력하고 종료 |
| `--config 경로` | 사용할 설정 JSON 파일 지정. 상대 경로는 현재 작업 디렉터리 기준 |
| `--once` | 시스템 상태 보고서를 한 번 전송 |
| `--reboot` | 일회 전송을 재부팅 시점 보고서로 표시 |
| `--loop` | 설정 주기로 계속 전송 |
| `--interval-minutes 분` | 반복 전송 또는 cron 생성에 사용할 주기 지정 |
| `--check-status` | 현재 머신의 설정된 업로드 디렉터리만 조회 |
| `--check-status-all` | `/tinyGW` 전체 노드 조회 |
| `--max-age-minutes 분` | 기록 지연 판단 기준. 기본값은 설정된 전송 주기의 2배 |
| `--status-output-dir 경로` | 상태 점검 JSON·tree 결과의 저장 디렉터리 |
| `--server-list 경로` | 서버 이름·IP·포트·디렉터리가 담긴 JSON 목록 사용 |
| `--print-crontab` | cron 등록용 명령만 출력 |
| `--install-crontab` | 현재 인자에 맞게 해당 설치 경로의 cron 작업 등록·교체 |
| `--iptime-list` | ipTIME 목록을 먼저 전송하고 일반 보고서도 전송 |
| `--gateway-watchdog` | Linux 기본 게이트웨이를 감시하며 연속 30분 ping 실패 시 재부팅 |
| `--gateway-dry-run` | `--gateway-watchdog`와 함께 사용해 실제 재부팅 없이 확인 |

`--check-status`와 `--check-status-all`은 동시에 사용할 수 없습니다. 상태 점검 옵션은
전송·재부팅·게이트웨이 감시·cron 출력/등록 옵션과도 함께 사용할 수 없습니다.
`--print-crontab`과 `--install-crontab` 역시 동시에 사용할 수 없습니다.

상태 점검에서 `--config`를 생략하면 crontab에서 설정 경로를 찾습니다.
일반 전송에서 생략하면 프로그램 디렉터리의 `settings.json`을 사용합니다.

상태 점검 결과는 기본적으로 workspace의
`workshot/2remember/server_list/server_status.json`과 `server_status.txt`에 저장됩니다.
시간은 서울 시간(`Asia/Seoul`, `KST` 또는 `+09:00`)으로 표시합니다.
Linux에서는 시작할 때 Docker 그룹 권한을 확인하고 필요한 경우 `WARNING`을 출력합니다.

설정 파일 작성, Docker 접근 권한, cron 등록, 게이트웨이 감시의 자세한 설명은
[README.md](README.md)를 참고하세요.


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
