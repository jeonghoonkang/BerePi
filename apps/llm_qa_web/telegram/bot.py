import json
import logging
import os
import urllib.error
import urllib.request

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters


TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
LLM_API_URL = os.environ.get("LLM_API_URL", "http://127.0.0.1:8001/api/ask")
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "").strip()
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "180"))
MAX_TELEGRAM_MESSAGE_LENGTH = 4096

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=os.environ.get("LOG_LEVEL", "INFO"),
)
logger = logging.getLogger(__name__)


def call_llm_api(prompt: str) -> str:
    payload = {"prompt": prompt}
    if LLM_PROVIDER:
        payload["provider"] = LLM_PROVIDER

    request = urllib.request.Request(
        LLM_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API 오류({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"API 서버에 연결할 수 없습니다: {exc.reason}") from exc

    answer = data.get("answer")
    if not answer:
        raise RuntimeError(f"API 응답에 answer가 없습니다: {data}")
    return answer


def split_message(text: str) -> list[str]:
    return [
        text[index : index + MAX_TELEGRAM_MESSAGE_LENGTH]
        for index in range(0, len(text), MAX_TELEGRAM_MESSAGE_LENGTH)
    ] or [""]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    await update.message.reply_text("프롬프트를 보내면 LLM API에 전달하고 답변을 회신합니다.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    await update.message.reply_text(
        "사용법:\n"
        "1. 이 채팅창에 질문이나 프롬프트를 입력합니다.\n"
        "2. 봇이 서버 API로 전송합니다.\n"
        "3. 생성된 답변을 다시 전달합니다."
    )


async def handle_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    prompt = (update.message.text or "").strip()
    if not prompt:
        await update.message.reply_text("프롬프트를 입력해 주세요.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    try:
        answer = call_llm_api(prompt)
    except Exception as exc:
        logger.exception("Failed to handle prompt")
        await update.message.reply_text(f"오류가 발생했습니다.\n{exc}")
        return

    for chunk in split_message(answer):
        await update.message.reply_text(chunk)


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN 환경 변수를 설정하세요.")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_prompt))

    logger.info("Telegram bot started. LLM_API_URL=%s", LLM_API_URL)
    application.run_polling()


if __name__ == "__main__":
    main()
