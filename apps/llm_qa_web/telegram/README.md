# Telegram Bot

텔레그램 사용자가 입력한 프롬프트를 LLM API 서버로 전송하고, API 응답의 `answer` 값을 다시 사용자에게 전달하는 봇입니다.

## 설치

```bash
cd BerePi/apps/llm_qa_web/telegram
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## 실행

먼저 LLM API 서버를 실행합니다.

```bash
cd ../
OPENAI_API_KEY="your-openai-api-key" PORT=8001 python3 server.py
```

다른 터미널에서 텔레그램 봇을 실행합니다.

```bash
cd telegram
export TELEGRAM_BOT_TOKEN="your-telegram-bot-token"
export LLM_API_URL="http://127.0.0.1:8001/api/ask"
python3 bot.py
```

## Qwen/OpenAI Dual API에 연결

`qwen_openai_dual_qa/api.py`의 FastAPI 서버를 사용할 때는 API 주소와 provider를 지정합니다.

```bash
export LLM_API_URL="http://127.0.0.1:8000/api/ask"
export LLM_PROVIDER="openai"
python3 bot.py
```

Qwen을 사용할 경우:

```bash
export LLM_PROVIDER="qwen"
python3 bot.py
```

## 환경 변수

- `TELEGRAM_BOT_TOKEN`: BotFather에서 발급받은 텔레그램 봇 토큰
- `LLM_API_URL`: 프롬프트를 보낼 API 주소, 기본값 `http://127.0.0.1:8001/api/ask`
- `LLM_PROVIDER`: 선택값. FastAPI Dual API 사용 시 `openai` 또는 `qwen`
- `REQUEST_TIMEOUT`: API 응답 대기 시간, 기본값 `180`
- `LOG_LEVEL`: 로그 레벨, 기본값 `INFO`
