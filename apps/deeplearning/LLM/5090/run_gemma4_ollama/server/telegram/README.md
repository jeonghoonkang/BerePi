# Telegram Bot

텔레그램 사용자가 입력한 프롬프트를 Gemma4 Ollama 서버의 `/api/generate`로 전달하고,
응답의 `response` 값을 다시 텔레그램으로 회신하는 봇입니다.

이 문서에서는 BerePi 저장소 절대 경로를 아래처럼 `BEREPI_DIR`로 가정합니다.

```bash
export BEREPI_DIR="/absolute/path/to/BerePi"
```

현재 코드는 `${BEREPI_DIR}/apps/deeplearning/LLM/5090/run_gemma4_ollama/server/telegram/bot.py`에서 아래 환경 변수를 읽어 동작합니다.

- `TELEGRAM_BOT_TOKEN`
- `LLM_API_URL`
- `GEMMA4_USER_ID`
- `GEMMA4_PASSWORD`
- `ALLOWED_TELEGRAM_USER_IDS`
- `ALLOWED_TELEGRAM_USER_IDS_FILE`
- `REQUEST_TIMEOUT`
- `LOG_LEVEL`
- `WRITING_TECH_DOC_TOOL_URL`
- `WRITING_TECH_DOC_TOOL_TIMEOUT`

즉, **토큰과 계정 정보는 소스 코드에 직접 하드코딩하지 않고 환경 변수로 주입하는 방식**이 현재 코드 기준의 권장 방법입니다.

## 1. 사전 준비

위 `BEREPI_DIR` 값을 실제 저장소 절대 경로로 바꿔서 사용합니다.

Gemma4 Ollama 서버 관련 파일 위치:

- 서버 디렉토리: `/absolute/path/to/BerePi/apps/deeplearning/LLM/5090/run_gemma4_ollama/server`
- 텔레그램 봇 디렉토리: `/absolute/path/to/BerePi/apps/deeplearning/LLM/5090/run_gemma4_ollama/server/telegram`
- 인증 샘플 파일: `/absolute/path/to/BerePi/apps/deeplearning/LLM/5090/run_gemma4_ollama/server/api_key.conf.sample`
- 텔레그램 봇 코드: `/absolute/path/to/BerePi/apps/deeplearning/LLM/5090/run_gemma4_ollama/server/telegram/bot.py`

## 2. 텔레그램 봇 추가 방법

### 2-1. Telegram에서 BotFather 실행

1. Telegram 앱에서 `@BotFather`를 검색해 대화를 엽니다.
2. `/start`를 입력합니다.
3. `/newbot`를 입력합니다.
4. 봇 이름을 입력합니다. 예: `BerePi Gemma4 Bot`
5. 봇 username을 입력합니다. username은 반드시 `bot`으로 끝나야 합니다. 예: `berepi_gemma4_bot`
6. 생성이 완료되면 BotFather가 HTTP API 토큰을 발급합니다.

발급 예시는 아래와 비슷합니다.

```text
1234567890:AAExampleYourTelegramBotTokenValue
```

이 값이 현재 코드에서 사용하는 `TELEGRAM_BOT_TOKEN` 값입니다.

### 2-2. 선택적으로 봇 기본 정보 설정

BotFather에서 아래 명령도 함께 설정하면 사용이 편합니다.

- `/setdescription` : 봇 설명 설정
- `/setabouttext` : 채팅 목록에 보일 소개 문구 설정
- `/setuserpic` : 봇 프로필 이미지 설정
- `/setcommands` : 명령어 목록 등록
- `/setinline` : Inline Mode 설정. 현재 운영 설정은 `On`
- `/setprivacy` : Group Privacy 설정. 현재 운영 설정은 `Off`

예시 명령어:

```text
start - 봇 사용 시작
help - 사용 방법 보기
boost - Markdown 기술 문서 보강
list - allom/boost 대상 파일 및 경로
ls - list 별칭
allom - WebDAV 메모 저장
findm - 메모와 원본 문서 검색
```

그룹 채팅에서 `@봇username 질문` 형태의 메시지를 받으려면 BotFather에서
Group Privacy가 `Off`로 설정되어 있어야 합니다. Privacy가 켜져 있으면 그룹의
일반 텍스트 메시지가 봇 프로세스까지 전달되지 않을 수 있습니다.

## 3. Gemma4 서버 인증 키 준비

텔레그램 봇은 Gemma4 서버의 `/api/generate`를 호출할 때 필요하면 사용자 ID와 비밀번호를 함께 보냅니다.
현재 서버는 `/absolute/path/to/BerePi/apps/deeplearning/LLM/5090/run_gemma4_ollama/server/api_key.conf`를 기준으로 인증을 검사합니다.

샘플 파일을 복사해서 실제 설정 파일을 만듭니다.

```bash
cp "${BEREPI_DIR}/apps/deeplearning/LLM/5090/run_gemma4_ollama/server/api_key.conf.sample" \
   "${BEREPI_DIR}/apps/deeplearning/LLM/5090/run_gemma4_ollama/server/api_key.conf"
```

예시:

```json
{
  "enabled": true,
  "allow_only_user": "admin",
  "users": [
    {
      "id": "admin",
      "password": "change-me-now",
      "enabled": true
    }
  ]
}
```

설정 포인트:

- `enabled: true` 이면 인증 사용
- `allow_only_user: "admin"` 이면 `admin` 계정만 허용
- `id` 값은 `GEMMA4_USER_ID`에 넣을 값
- `password` 값은 `GEMMA4_PASSWORD`에 넣을 값

운영 환경에서는 `change-me-now` 같은 예시 비밀번호를 실제 비밀번호로 반드시 변경하세요.

인증을 사용하지 않으려면 `enabled`를 `false`로 바꾸면 되고, 이 경우 텔레그램 봇 실행 시 `GEMMA4_USER_ID`와 `GEMMA4_PASSWORD`를 생략할 수 있습니다.

## 4. 현재 코드에 key 값을 넣는 방법

현재 코드는 `/absolute/path/to/BerePi/apps/deeplearning/LLM/5090/run_gemma4_ollama/server/telegram/bot.py`에서 아래처럼 환경 변수를 읽습니다.

- `TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")`
- `LLM_API_URL = os.environ.get("LLM_API_URL", "http://127.0.0.1:8082/api/generate")`
- `GEMMA4_USER_ID = os.environ.get("GEMMA4_USER_ID", "").strip()`
- `GEMMA4_PASSWORD = os.environ.get("GEMMA4_PASSWORD", "")`

따라서 key 값을 넣는 방법은 아래 2가지가 있습니다.

### 방법 A. 권장: 실행 전에 환경 변수로 주입

```bash
export TELEGRAM_BOT_TOKEN="BotFather에서_받은_토큰"
export LLM_API_URL="http://127.0.0.1:8082/api/generate"
export GEMMA4_USER_ID="admin"
export GEMMA4_PASSWORD="실제_서버_비밀번호"
export ALLOWED_TELEGRAM_USER_IDS="123456789,987654321"
```

이 방식은 소스 파일 수정 없이 안전하게 키를 주입할 수 있어 권장됩니다.

`ALLOWED_TELEGRAM_USER_IDS`를 설정하면 지정된 Telegram 사용자 숫자 ID만 봇을 사용할 수 있습니다.
값을 비워두면 모든 사용자를 허용합니다. 개인별 숫자 ID는 Telegram에서 `@userinfobot`에게
메시지를 보내 확인할 수 있습니다.

여러 ID를 파일로 관리하려면 `allowed_telegram_user_ids_sample.txt`를 `allowed_telegram_user_ids.txt`로 복사한 뒤,
숫자 ID를 한 줄에 하나씩 저장합니다.
기본 파일 경로는 텔레그램 봇 디렉토리의 `allowed_telegram_user_ids.txt`이며,
`ALLOWED_TELEGRAM_USER_IDS_FILE`로 다른 파일을 지정할 수 있습니다.

### 방법 B. 비권장: `bot.py`에 직접 문자열 입력

직접 넣으려면 `/absolute/path/to/BerePi/apps/deeplearning/LLM/5090/run_gemma4_ollama/server/telegram/bot.py`의 환경 변수 부분을 고정 문자열로 바꾸면 됩니다.
하지만 토큰과 비밀번호가 파일에 남기 때문에 권장하지 않습니다.

예를 들어 아래 항목들이 직접 값이 들어가는 위치입니다.

- `TELEGRAM_BOT_TOKEN`
- `GEMMA4_USER_ID`
- `GEMMA4_PASSWORD`

가능하면 방법 A를 사용하세요.

## 5. 설치

```bash
cd "${BEREPI_DIR}/apps/deeplearning/LLM/5090/run_gemma4_ollama/server/telegram"
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

서버 스크립트에 실행 권한이 없다면 최초 1회만 아래 명령을 실행합니다.

```bash
cd "${BEREPI_DIR}/apps/deeplearning/LLM/5090/run_gemma4_ollama/server"
chmod +x run_service.sh start.sh stop.sh
```

## 6. 실행 방법

### `run_service.sh`와 함께 자동 실행

`server/run_service.sh`는 웹 서버 시작 시 Telegram 봇을 자동 실행합니다.
웹 서버가 봇 프로세스를 관리하며 Ctrl+C 또는 SIGTERM으로 종료하면 봇도 종료합니다.
`start.sh`는 별도 실행 방식이며 이 자동 실행 기능을 사용하지 않습니다.

최초 한 번 위 설치 절차로 봇 의존성을 설치하고, `telegram/this_conf_keys.sh`에
다음 환경변수를 설정하세요. 이 파일은 Git에서 제외됩니다.

```bash
export TELEGRAM_BOT_TOKEN="BotFather에서_받은_토큰"
export GEMMA4_USER_ID="실제_서버_사용자"
export GEMMA4_PASSWORD="실제_서버_비밀번호"
export ALLOWED_TELEGRAM_USER_IDS="123456789"
```

```bash
# server 디렉토리에서 실행
bash run_service.sh
bash run_service.sh 2500 0
# Telegram 없이 실행
TELEGRAM_ENABLED=0 bash run_service.sh
```

- 토큰은 기존 환경변수로 전달해도 됩니다. 설정 파일이 있으면 해당 파일을 읽습니다.
- `LLM_API_URL`을 설정하지 않으면 이번 서버 포트에 맞게 자동 지정합니다.
  기존 설정 파일에 `8082`가 고정되어 있다면 해당 줄을 제거하거나 수정하세요.
- Python은 `TELEGRAM_PYTHON`, `telegram/.venv/bin/python`,
  `telegram/install/bin/python`, 시스템 `python3` 순으로 선택합니다.
- `TELEGRAM_CONFIG_FILE`로 다른 설정 파일을 지정할 수 있습니다.
- 로그는 서버 로그 디렉토리의 `telegram-bot.log`에 저장됩니다.
- 토큰이 없거나 봇 시작이 실패해도 서버는 계속 실행됩니다. 로그를 확인하세요.
- 프로세스 잠금으로 관리되는 봇은 한 번만 실행됩니다. 수동 `run_bot.sh`는 Linux의 `flock` 명령이 필요합니다.
  기존 cron이나 수동 `python3 bot.py` 실행은 먼저 중지하세요. 기존 cron의 봇 실행
  및 재시작 항목을 함께 사용하면 중복 polling이 발생할 수 있습니다.
- 실행 중 봇이 종료되면 자동 재시작하지 않습니다. 서버를 재시작하면 다시 실행합니다.

### 웹 Telegram 탭

1. 웹화면의 **Server** 탭에서 사용자 ID와 비밀번호로 로그인합니다.
2. **Telegram** 탭에서 봇 토큰, LLM API URL, 서버 인증정보, 허용 사용자 ID,
   봇 사용자 이름을 입력하고 **설정 저장**을 누릅니다.
3. **시작**, **중지**, **재시작**으로 이 웹 서버가 관리하는 봇을 제어합니다.
   실행 중 설정을 변경했다면 **재시작**해야 적용됩니다.

상태는 5초마다 갱신됩니다. 토큰·비밀번호는 화면/API에 반환하지 않으며,
비워서 저장하면 기존 값을 유지합니다. **설정 불러오기**는 저장된 값으로 입력을 초기화합니다.
웹 설정은 Git에서 제외되는 `telegram/web_config.json`에 저장하며,
기존 환경변수와 `this_conf_keys.sh`보다 우선합니다. 셸 명령은 웹에서 입력하거나 실행하지 않습니다.
`ALLOWED_TELEGRAM_USER_IDS`와 기존 `allowed_telegram_user_ids.txt`의 ID는 합쳐서 적용됩니다.

다른 `run_service.sh` 또는 `run_bot.sh`가 이미 봇을 실행하면 중복 실행을 막고
다른 서비스에서 실행 중으로 표시합니다. 수동 `python3 bot.py`나 기존 cron은
이 잠금을 사용하지 않으므로 별도로 중지해야 합니다.
웹 설정은 이 웹 서버의 봇 관리에 적용되며 수동 `run_bot.sh`는 기존 셸 설정을 사용합니다.

### 6-1. 먼저 Gemma4 Ollama 서버 실행

```bash
cd "${BEREPI_DIR}/apps/deeplearning/LLM/5090/run_gemma4_ollama/server"
./start.sh
```

정상 실행 후 확인:

- 웹 UI: `http://127.0.0.1:8082`
- API: `http://127.0.0.1:8082/api/generate`

다른 장비에서 텔레그램 봇이 API에 접근해야 한다면 `LLM_API_URL`을 해당 서버 IP로 지정합니다.
예:

```bash
export LLM_API_URL="http://192.168.0.10:8082/api/generate"
```

### 6-2. 텔레그램 봇 실행

다른 터미널에서 실행합니다.

```bash
cd "${BEREPI_DIR}/apps/deeplearning/LLM/5090/run_gemma4_ollama/server/telegram"
. .venv/bin/activate
export TELEGRAM_BOT_TOKEN="BotFather에서_받은_토큰"
export LLM_API_URL="http://127.0.0.1:8082/api/generate"
export GEMMA4_USER_ID="admin"
export GEMMA4_PASSWORD="실제_서버_비밀번호"
export ALLOWED_TELEGRAM_USER_IDS="123456789,987654321"
python3 bot.py
```

인증을 끈 경우:

```bash
cd "${BEREPI_DIR}/apps/deeplearning/LLM/5090/run_gemma4_ollama/server/telegram"
. .venv/bin/activate
export TELEGRAM_BOT_TOKEN="BotFather에서_받은_토큰"
export LLM_API_URL="http://127.0.0.1:8082/api/generate"
python3 bot.py
```

실행되면 polling 방식으로 텔레그램 메시지를 계속 대기합니다.

## 7. 사용 방법

### 7-1. Telegram에서 봇 열기

1. Telegram에서 생성한 봇 username을 검색합니다.
2. 봇 대화창에서 `시작` 또는 `/start`를 누릅니다.
3. 필요하면 `/help`를 입력해 사용법을 확인합니다.

### 7-2. 프롬프트 보내기

채팅창에 일반 메시지로 질문을 입력하면 그대로 Gemma4 서버에 전달됩니다.

예시:

```text
라즈베리파이에서 Ollama를 사용할 때 주의할 점을 5가지 정리해 줘.
```

동작 순서:

1. Telegram 메시지가 봇에 도착
2. 봇이 `typing` 상태를 표시
3. `bot.py`가 `LLM_API_URL`로 POST 요청 전송
4. Gemma4 서버가 응답 생성
5. 봇이 응답을 다시 텔레그램으로 회신

응답이 길면 텔레그램 제한(4096자)에 맞춰 여러 메시지로 나누어 전송합니다.

일반 프롬프트 응답 끝에는 LLM 처리 시간·모델·큐 정보에 이어 `[Telegram]` 요약이 붙습니다.
여기에는 현재 채팅 종류와 제목, 서버 대화 분리에 사용하는 `Room ID`(`chat_id:topic_id`),
봇 사용자명이 표시됩니다. 토큰, 서버 비밀번호, 발신자 개인 ID는 응답에 표시하지 않습니다.
주제(포럼) 메시지가 아닌 경우 `topic_id`는 `0`입니다.

## 8. 자주 사용하는 명령

- `/start` : 봇 소개 메시지 표시
- `/help` : 사용 방법 표시
- `/boost [--dry-run] [파일명]` : 전체 또는 특정 Markdown 문서를 보강. 먼저 `--dry-run` 사용 권장
- `/list`, `/ls` : `allom` 메모와 `boost` 원본·결과 파일 경로 표시
- `/allom 메모 내용` : 메모를 `memo_alloc_YYYYMMDD_HHMMSS.md`로 WebDAV에 저장
- `/findm [--page-size N] 검색어` : 메모와 `boost` 원본에서 관련 문장 검색
- 일반 텍스트 메시지 : Gemma4 프롬프트로 처리

문서 명령은 Telegram 봇이 직접 WebDAV 비밀번호를 갖는 대신 Gemma4 서버의 인증된 `/api/tools/writing-tech-doc`을 호출합니다. Gemma4 서버 프로세스에는 `WRITING_TECH_DOC_CLI`와 `WRITING_TECH_DOC_CONFIG`가 설정되어 있어야 합니다. 봇과 API 서버가 다른 주소라면 봇에 다음 값을 지정합니다.

```bash
export WRITING_TECH_DOC_TOOL_URL="http://SERVER_IP:8082/api/tools/writing-tech-doc"
export WRITING_TECH_DOC_TOOL_TIMEOUT="960"
```

## 9. 허용 사용자 ID 관리

개인별 Telegram 숫자 ID는 Telegram에서 `@userinfobot`에게 메시지를 보내 확인할 수 있습니다.
확인한 숫자 ID는 `allowed_user_ids.sh`로 `allowed_telegram_user_ids.txt`에 추가하거나 삭제합니다.

```bash
cd "${BEREPI_DIR}/apps/deeplearning/LLM/5090/run_gemma4_ollama/server/telegram"
cp allowed_telegram_user_ids_sample.txt allowed_telegram_user_ids.txt
./allowed_user_ids.sh add 123456789 987654321
./allowed_user_ids.sh list
./allowed_user_ids.sh delete 123456789 987654321
```

`add`는 기존 ID 목록을 유지하면서 새 ID를 하나 이상 추가합니다. 이미 같은 ID가 있으면 중복 저장하지 않습니다.
`delete` 또는 `remove`는 지정한 ID를 하나 이상 목록에서 삭제합니다.

환경변수 형태로 보고 싶으면 아래 명령을 사용할 수 있습니다.

```bash
./allowed_user_ids.sh export
```

## 10. 문제 해결

### `TELEGRAM_BOT_TOKEN 환경 변수를 설정하세요.`

텔레그램 토큰이 설정되지 않은 상태입니다.

```bash
export TELEGRAM_BOT_TOKEN="BotFather에서_받은_토큰"
```

### `API 서버에 연결할 수 없습니다`

- Gemma4 서버가 실행 중인지 확인
- `LLM_API_URL` 주소가 올바른지 확인
- 방화벽 또는 포트(`8082`) 접근 가능 여부 확인

서버 확인 예시:

```bash
curl -X POST "http://127.0.0.1:8082/api/generate" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"admin","password":"실제_서버_비밀번호","prompt":"hello"}'
```

### `API 오류(401)` 또는 인증 실패

- `api_key.conf`의 `id`, `password`, `enabled` 값을 다시 확인
- `allow_only_user`에 다른 계정이 지정되어 있지 않은지 확인
- 텔레그램 봇의 `GEMMA4_USER_ID`, `GEMMA4_PASSWORD` 값이 동일한지 확인

### 응답이 너무 느린 경우

기본 대기 시간은 `180`초입니다. 필요하면 늘릴 수 있습니다.

```bash
export REQUEST_TIMEOUT="300"
```

## 11. 환경 변수 정리

- `TELEGRAM_BOT_TOKEN`: BotFather에서 발급받은 텔레그램 봇 토큰
- `LLM_API_URL`: 프롬프트를 보낼 API 주소, 기본값 `http://127.0.0.1:8082/api/generate`
- `GEMMA4_USER_ID`: `api_key.conf`에 등록된 사용자 ID
- `GEMMA4_PASSWORD`: `api_key.conf`에 등록된 비밀번호
- `ALLOWED_TELEGRAM_USER_IDS`: 봇 사용을 허용할 Telegram 사용자 숫자 ID 목록. 콤마로 구분하며, 비어 있으면 모든 사용자 허용
- `ALLOWED_TELEGRAM_USER_IDS_FILE`: 허용할 Telegram 사용자 숫자 ID를 한 줄에 하나씩 저장한 파일. 기본값은 `allowed_telegram_user_ids.txt`
- `REQUEST_TIMEOUT`: API 응답 대기 시간, 기본값 `180`
- `LOG_LEVEL`: 로그 레벨, 기본값 `INFO`
- `WRITING_TECH_DOC_TOOL_URL`: 문서 도구 API 주소. 기본값은 `LLM_API_URL`과 같은 서버의 `/api/tools/writing-tech-doc`
- `WRITING_TECH_DOC_TOOL_TIMEOUT`: 문서 도구 API 대기 시간, 기본값 `960`초

## 12. 보안 주의 사항

- `TELEGRAM_BOT_TOKEN`을 Git 저장소에 커밋하지 마세요.
- `api_key.conf`는 `.gitignore`에 포함되어 있으므로 실제 운영 키는 이 파일에 두고 커밋하지 않는 것이 안전합니다.
- `allowed_telegram_user_ids.txt`는 `.gitignore`에 포함되어 있으므로 실제 Telegram 사용자 ID는 이 파일에 두고 커밋하지 않는 것이 안전합니다.
- 운영 환경에서는 예시 비밀번호 대신 충분히 긴 실제 비밀번호를 사용하세요.

## 13. MTProto 사용자 계정 연동을 기본 방식으로 사용하지 않는 이유

MTProto 자체가 금지된 방식은 아닙니다. 다만 봇을 만들지 않고 일반 Telegram 사용자 계정으로
로그인하는 MTProto 클라이언트(일명 user client 또는 userbot)는 이 서버의 명령 처리 용도에는
기본적으로 권장하지 않습니다. `chat_id`는 메시지를 보낼 대상을 식별하는 값일 뿐 인증 정보가
아니므로, 채팅방 ID만으로 연결할 수도 없습니다.

주요 부정적 이유는 다음과 같습니다.

- **개인 계정 전체에 영향을 줄 수 있습니다.** MTProto 사용자 인증 후의 API 호출은 로그인한
  사용자 신원으로 실행됩니다. 세션 파일 또는 authorization key가 유출되면 전용 봇 토큰 유출보다
  영향 범위가 커질 수 있으며, 해당 계정이 접근 가능한 개인 대화와 그룹도 위험 범위에 들어갑니다.
- **인증 정보와 세션 관리가 더 복잡합니다.** 별도의 `api_id`, `api_hash`, 전화번호 인증 코드,
  선택적인 2단계 인증 비밀번호가 필요합니다. 장기 실행 서비스에서는 세션 파일 암호화, 재로그인,
  세션 폐기 및 복구 절차도 직접 관리해야 합니다.
- **계정 제한 또는 영구 정지 위험이 있습니다.** Telegram은 비공식 API 클라이언트로 로그인한
  계정을 오용 방지를 위해 관찰한다고 명시하며, flooding·spamming 등에 API를 사용하면 영구 정지될
  수 있다고 안내합니다. LLM 자동 응답의 반복 전송이나 잘못된 재시도도 보수적인 rate limit과
  차단 로직 없이 운영하면 위험을 높입니다.
- **사용자 동의 없는 자동 동작은 약관 문제가 될 수 있습니다.** Telegram API 약관은 사용자의
  인지와 동의 없이 사용자 대신 행동하는 것을 금지합니다. 개인 계정을 상시 자동화하면 봇 계정에
  비해 사람의 메시지와 자동 동작의 경계가 불명확해질 수 있습니다.
- **오류 및 연결 상태 처리가 늘어납니다.** `FLOOD_WAIT`, slow mode, 인증 키 중복, 연결 재수립,
  업데이트 순서와 누락 복구 등을 처리해야 합니다. 동일 세션을 여러 서버에 복사해 병렬 실행하면
  인증 키가 무효화되어 다시 로그인해야 할 수도 있습니다.
- **최소 권한 분리가 어렵습니다.** Bot API는 전용 봇 계정에 필요한 방 권한만 줄 수 있지만,
  사용자 계정 세션은 보통 더 넓은 권한과 대화 범위를 가집니다. 문서 검색·저장 명령 하나를 위해
  개인 계정 권한 전체를 서버에 위임하는 것은 권한 범위가 과도합니다.
- **현재 운영 구조와 기능이 중복됩니다.** 현재 구현은 Bot API 토큰, 허용 사용자 ID, 명시적인
  slash 명령, 웹 기반 시작·중지 및 로그 관리로 범위를 제한합니다. MTProto를 함께 지원하면 별도의
  라이브러리, 세션 저장소, 인증 화면, 모니터링 및 장애 복구 경로를 추가로 유지해야 합니다.

따라서 현재 요구사항은 **Bot API + 대상 `chat_id`/토픽 ID + 허용 사용자 ID 목록**으로 운영하는
것을 권장합니다. Bot API로 불가능한 사용자 전용 기능이 반드시 필요한 경우에만 MTProto를 별도
옵션으로 검토하고, 개인 주계정이 아닌 분리된 계정, 최소 그룹 권한, 암호화된 세션 저장소, 전송률
제한, 감사 로그, 즉시 중지 스위치와 세션 폐기 절차를 먼저 마련해야 합니다. 계정 생성과 자동화는
Telegram의 최신 약관 및 운영 정책을 충족해야 합니다.

관련 Telegram 공식 문서:

- [API ID 발급 및 비공식 클라이언트 오용 경고](https://core.telegram.org/api/obtaining_api_id)
- [사용자 인증과 authorization key](https://core.telegram.org/api/auth)
- [Telegram API 이용 약관](https://core.telegram.org/api/terms)
- [API 오류와 FLOOD_WAIT 처리](https://core.telegram.org/api/errors)
- [HTTP 기반 Telegram Bot API](https://core.telegram.org/bots/api)
