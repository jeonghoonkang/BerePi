# 외부 LLM Routing HTTP Heartbeat

별도의 서버에서 `llm_routing`의 `/health`와 인증된 `/api/status`를 주기적으로 조회하여 Telegram으로 장애와 복구를 알립니다. Python 3.10 이상만 필요하며 추가 패키지는 없습니다. 디렉터리 이름 `http_hearbeat`는 요청한 이름을 그대로 사용합니다.

## 설정 및 실행

```bash
cd apps/telegram/http_hearbeat
cp config.example.json config.json
chmod 600 config.json
```

`config.json`의 `url`을 외부에서 접근할 라우팅 사이트 주소로 변경하고 아래 값을 채웁니다. URL에 경로 접두어가 있다면 유지합니다. 외부 연결에는 HTTPS를 권장합니다.

| 설정 | 설명 | 우선 적용 환경변수 |
|---|---|---|
| `bot_token` | BotFather에서 발급한 봇 토큰 | `TELEGRAM_BOT_TOKEN` |
| `chat_id` | 알림을 받을 사용자/그룹/채널 ID | `TELEGRAM_CHAT_ID` |
| `password` | llm_routing API 비밀번호 | `LLM_ROUTING_PASSWORD` |
| `url` | 라우팅 사이트 기본 주소 | `LLM_ROUTING_URL` |

봇 토큰만으로는 수신자를 정할 수 없어 `chat_id`도 필요합니다. 개인 채팅에서는 먼저 봇에게 `/start`를 보내세요. [Telegram Bot API](https://core.telegram.org/bots/api#getupdates)의 `getUpdates` 응답에서 본인이 보낸 메시지의 `message.chat.id`를 확인할 수 있습니다. 웹훅을 사용하는 기존 봇은 `getUpdates`와 병행할 수 없으므로 기존 설정의 수신자 ID를 이용하세요. 다른 사람이 보낸 첫 메시지를 자동으로 수신자로 등록하지 않습니다.

```bash
# 실제 상태 조회만 수행: Telegram 전송/상태 저장 없음
python3 heartbeat.py --dry-run

# 한 번 점검하고 알림 정책에 따라 전송
python3 heartbeat.py --once

# 지속 감시
python3 heartbeat.py
```

종료 코드: `0` 정상, `1` 점검 이상, `2` 설정/상태 파일 오류 또는 단발 실행에서 알림 전송 실패. `--once`도 연속 실패 임계값을 적용하므로 기본 설정에서 첫 장애에는 전송하지 않습니다. 즉시 장애 알림이 필요하면 `failure_threshold`를 `1`로 설정하세요. 정상 최초 실행에서는 감시 시작 메시지를 보냅니다.

## 판정 및 알림

- `/health` 연결 실패, HTTP 오류, 비정상 JSON, `ok != true`를 감지합니다.
- 인증된 상세 상태의 활성 대상마다 `metrics.status`, `available_targets`, `last_health_probe_at`을 검사합니다. 모델명과 서버 주소를 알림에 표시합니다.
- 상세 정보가 없는 공개 응답은 인증/응답 형식 오류로 처리합니다. 공개 응답의 `ready`만으로 정상이라고 판단하지 않습니다.
- 대상이 없거나 상태가 unknown/error인 경우, 가용 대상 수가 0 이하인 경우, 점검 정보가 오래되거나 없는 경우 알립니다. `available_targets=null`은 일부 백엔드에서 가용 수를 제공하지 않는 의미이므로 이것만으로 실패 처리하지 않습니다.
- 비활성 대상은 제외합니다. 기존 장애 대상의 비활성화/삭제는 복구/해제로 알립니다. 라우터에 연결할 수 없을 때는 기존 모델 장애가 복구되었다고 판단하지 않습니다.
- 기본 2회 연속 실패 후 알림, 정상 확인 시 복구 알림, 동일 장애는 기본 1시간마다 재알림합니다. `state.json`에 상태를 저장하여 프로세스 재시작 후에도 유지합니다. 전송 실패는 다음 점검에서 재시도합니다.
- 기본 점검 간격은 점검 완료 후 60초입니다. 타임아웃 120초, 오래된 정보 기준 300초를 대상 수와 라우터 내부 점검 주기에 맞게 조정하세요. 라우터는 상세 조회 시 대상들을 순차 점검할 수 있습니다.

이 도구는 라우터가 제공하는 백엔드 상태를 감시합니다. 모델별 실제 추론 결과, 운영체제 프로세스, 라우터에 등록되지 않은 서비스까지 검증하지는 않습니다. 실제 프롬프트 생성 검사는 기존 `apps/deeplearning/LLM/llm_routing/test_routing/check_routing.py`를 이용하세요. 감시 서버 자체가 중단되면 알림을 보낼 수 없으므로 운영 라우터와 별도 시스템에서 실행하세요.

서버 오류 응답 본문은 토큰 등의 노출을 피하기 위해 알림에 포함하지 않습니다. 로그에는 모델/서버 식별정보와 요약 원인을 출력합니다. 하나의 설정 디렉터리에서는 프로세스 하나만 실행하세요. 여러 사이트는 각각 별도의 설정 디렉터리 및 서비스 인스턴스로 운영합니다.

## Linux systemd 등록

외부 감시 서버에 이 디렉터리의 파일들을 복사한 뒤 다음과 같이 설정합니다.

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin llm-monitor
sudo mkdir -p /opt/http_hearbeat
sudo cp heartbeat.py config.example.json http-hearbeat.service /opt/http_hearbeat/
sudo cp /opt/http_hearbeat/config.example.json /opt/http_hearbeat/config.json
sudo touch /opt/http_hearbeat/.env
sudo chmod 600 /opt/http_hearbeat/config.json /opt/http_hearbeat/.env
sudo chown -R llm-monitor:llm-monitor /opt/http_hearbeat
sudoedit /opt/http_hearbeat/config.json
sudoedit /opt/http_hearbeat/.env
```

`.env` 예시 (systemd용이며 `export`는 붙이지 않습니다. 직접 Python 실행 시에는 이 파일을 자동 로드하지 않습니다):

```ini
TELEGRAM_BOT_TOKEN=봇토큰
TELEGRAM_CHAT_ID=수신채팅ID
LLM_ROUTING_PASSWORD=라우팅비밀번호
```

```bash
sudo cp /opt/http_hearbeat/http-hearbeat.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now http-hearbeat
sudo systemctl status http-hearbeat
sudo journalctl -u http-hearbeat -f
```

`config.json`, `.env`, `state.json`은 Git에서 제외합니다. 설정이나 환경변수를 바꾸면 서비스를 재시작하세요.

## 테스트

```bash
python3 -m unittest discover -s apps/telegram/http_hearbeat -p 'test_*.py' -v
```

테스트는 로컬 HTTP 서버와 가짜 전송 함수를 사용하며 운영 사이트 접속이나 실제 Telegram 메시지 발송을 하지 않습니다.
