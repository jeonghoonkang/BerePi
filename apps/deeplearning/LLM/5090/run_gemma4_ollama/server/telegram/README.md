# Telegram Bot

텔레그램 사용자가 입력한 프롬프트를 현재 디렉토리의 Gemma4 Ollama 서버로 전송하고,
API 응답의 `response` 값을 다시 사용자에게 전달하는 봇입니다.

## 설치

```bash
cd /home/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/run_gemma4_ollama/server/telegram
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## 실행

먼저 Gemma4 Ollama 서버를 실행합니다.

```bash
cd /home/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/run_gemma4_ollama/server
./start.sh
```

다른 터미널에서 텔레그램 봇을 실행합니다.

```bash
cd /home/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/run_gemma4_ollama/server/telegram
export TELEGRAM_BOT_TOKEN="your-telegram-bot-token"
export LLM_API_URL="http://127.0.0.1:8082/api/generate"
export GEMMA4_USER_ID="admin"
export GEMMA4_PASSWORD="change-me-now"
python3 bot.py
```

`api_key.conf`에서 인증을 비활성화한 경우 `GEMMA4_USER_ID`와 `GEMMA4_PASSWORD`는 생략할 수 있습니다.

## 환경 변수

- `TELEGRAM_BOT_TOKEN`: BotFather에서 발급받은 텔레그램 봇 토큰
- `LLM_API_URL`: 프롬프트를 보낼 API 주소, 기본값 `http://127.0.0.1:8082/api/generate`
- `GEMMA4_USER_ID`: `api_key.conf`에 등록된 사용자 ID
- `GEMMA4_PASSWORD`: `api_key.conf`에 등록된 비밀번호
- `REQUEST_TIMEOUT`: API 응답 대기 시간, 기본값 `180`
- `LOG_LEVEL`: 로그 레벨, 기본값 `INFO`
