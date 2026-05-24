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

여러 ID를 파일로 관리하려면 `allowed_telegram_user_ids.txt`에 숫자 ID를 한 줄에 하나씩 저장합니다.
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

## 8. 자주 사용하는 명령

- `/start` : 봇 소개 메시지 표시
- `/help` : 사용 방법 표시
- 일반 텍스트 메시지 : Gemma4 프롬프트로 처리

## 9. 허용 사용자 ID 관리

개인별 Telegram 숫자 ID는 Telegram에서 `@userinfobot`에게 메시지를 보내 확인할 수 있습니다.
확인한 숫자 ID는 `allowed_user_ids.sh`로 `allowed_telegram_user_ids.txt`에 추가하거나 삭제합니다.

```bash
cd "${BEREPI_DIR}/apps/deeplearning/LLM/5090/run_gemma4_ollama/server/telegram"
./allowed_user_ids.sh add 123456789
./allowed_user_ids.sh list
./allowed_user_ids.sh delete 123456789
```

`add`는 기존 ID 목록을 유지하면서 새 ID 하나를 추가합니다. 이미 같은 ID가 있으면 중복 저장하지 않습니다.
`delete` 또는 `remove`는 지정한 ID 하나를 목록에서 삭제합니다.

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

## 12. 보안 주의 사항

- `TELEGRAM_BOT_TOKEN`을 Git 저장소에 커밋하지 마세요.
- `api_key.conf`는 `.gitignore`에 포함되어 있으므로 실제 운영 키는 이 파일에 두고 커밋하지 않는 것이 안전합니다.
- 운영 환경에서는 예시 비밀번호 대신 충분히 긴 실제 비밀번호를 사용하세요.
