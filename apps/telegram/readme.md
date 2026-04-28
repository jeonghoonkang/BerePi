## 개요
`apps/telegram`은 텔레그램 봇을 이용해 서버 상태와 로컬 장비 정보를 전송하는 도구 모음입니다.

## 포함된 기능
### 1. `diskreport`
- 디스크 여유 공간을 GB 단위로 계산해 텔레그램으로 전송합니다.
- 로컬 네트워크 IP 주소를 함께 포함합니다.
- 전송 시각은 `Asia/Seoul` 기준으로 기록됩니다.
- `telegramconfig.json`의 `telegram_bot_setting` 배열을 순회하며 여러 수신자에게 동시에 전송할 수 있습니다.
- 개별 수신자 전송 실패가 발생해도 전체 실행이 중단되지 않도록 예외를 무시합니다.
- 주기 실행을 위한 `crontab` 예시가 포함되어 있습니다.
- 상세: [apps/telegram/diskreport/readme.md](/Users/tinyos/devel_opment/BerePi/apps/telegram/diskreport/readme.md)

### 2. `netreport`
- `nmap` 기반 로컬 포트 스캔 결과를 텔레그램으로 전송합니다.
- 각 호스트에 대해 공인 IP, 호스트 상태, 프로토콜별 오픈 포트와 서비스 이름을 정리합니다.
- 실행 장비의 로컬 IP 주소도 함께 전송합니다.
- 메시지는 Markdown 포맷으로 발송됩니다.
- `telegramconfig.json`에서 단일 봇 토큰과 채팅 ID를 읽어 전송합니다.
- 직접 실행 및 `crontab` 실행 예시가 포함되어 있습니다.
- 상세: [apps/telegram/netreport/readme.md](/Users/tinyos/devel_opment/BerePi/apps/telegram/netreport/readme.md)

### 3. `cli_send`
- `telegram-send` CLI를 이용해 쉘 환경에서 텍스트와 파일을 전송할 수 있습니다.
- `crontab_sh.sh`는 장비 상태 정보를 수집해 텔레그램으로 보내는 예시 스크립트입니다.
- 스크립트는 날짜, CPU 온도(`vcgencmd measure_temp`), 디스크 사용량(`df -h`), 네트워크 정보(`ifconfig`)를 수집합니다.
- 전송 시 `inet6`, `tmpfs` 등의 불필요한 행을 제외하고 상위 70줄만 발송합니다.
- `systemd service/timer` 등록 예시 문서가 포함되어 있어 부팅 후 자동 실행이나 주기 실행에 사용할 수 있습니다.
- 상세:
  [apps/telegram/cli_send/readme.md](/Users/tinyos/devel_opment/BerePi/apps/telegram/cli_send/readme.md),
  [apps/telegram/cli_send/crontab_sh.md](/Users/tinyos/devel_opment/BerePi/apps/telegram/cli_send/crontab_sh.md),
  [apps/telegram/cli_send/service_registration.md](/Users/tinyos/devel_opment/BerePi/apps/telegram/cli_send/service_registration.md)

## 공통 설정
- 텔레그램 봇 토큰과 채팅 ID가 필요합니다.
- 봇 API 사용 방법 참고: [python-telegram-bot 문서](http://python-telegram-bot.readthedocs.io/en/latest/index.html)
- 채널을 생성해 여러 사람과 상태 메시지를 공유할 수 있습니다.

## 참고 사항
- `diskreport`와 `netreport`는 네트워크 인터페이스 이름을 코드에서 `enp1s0`으로 가정합니다.
- 실행 환경에 따라 인터페이스 이름이 다르면 코드에서 해당 값을 변경해야 합니다.
- `netreport`는 `python-telegram-bot`, `python-nmap`, `requests`, `pytz` 의존성이 필요합니다.
- `diskreport`는 `python-telegram-bot`, `requests`, `pytz` 의존성이 필요합니다.
- `cli_send`는 `telegram-send` 설치와 사전 설정이 필요합니다.
