import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from telegram import Update
from telegram.constants import ChatAction, ChatType
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters


TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_BOT_USERNAMES = {
    username.strip().lstrip("@").lower()
    for username in os.environ.get(
        "TELEGRAM_BOT_USERNAMES",
        os.environ.get("TELEGRAM_BOT_USERNAME", "berepi_gemma_bot,berepi_gemma_model,model_gemma"),
    ).split(",")
    if username.strip()
}
LLM_API_URL = os.environ.get("LLM_API_URL", "http://127.0.0.1:8082/api/generate")
GEMMA4_USER_ID = os.environ.get("GEMMA4_USER_ID", "").strip()
GEMMA4_PASSWORD = os.environ.get("GEMMA4_PASSWORD", "")
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "180"))
MAX_TELEGRAM_MESSAGE_LENGTH = 4096
MAX_PENDING_UPDATES_ON_STARTUP = int(os.environ.get("MAX_PENDING_UPDATES_ON_STARTUP", "10"))
ALLOWED_TELEGRAM_USER_IDS_FROM_ENV = {
    user_id.strip()
    for user_id in os.environ.get("ALLOWED_TELEGRAM_USER_IDS", "").split(",")
    if user_id.strip()
}
ALLOWED_TELEGRAM_USER_IDS_FILE = Path(
    os.environ.get("ALLOWED_TELEGRAM_USER_IDS_FILE", Path(__file__).resolve().with_name("allowed_telegram_user_ids.txt"))
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=os.environ.get("LOG_LEVEL", "INFO"),
)
logger = logging.getLogger(__name__)


def call_llm_api(prompt: str) -> str:
    payload = {"prompt": prompt}
    if GEMMA4_USER_ID or GEMMA4_PASSWORD:
        payload["user_id"] = GEMMA4_USER_ID
        payload["password"] = GEMMA4_PASSWORD

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

    answer = data.get("response") or data.get("answer")
    if not answer:
        raise RuntimeError(f"API 응답에 response가 없습니다: {data}")

    elapsed_line = data.get("elapsed_line")
    if elapsed_line:
        return f"{answer}\n\n{elapsed_line}"
    return answer


def split_message(text: str) -> list[str]:
    return [
        text[index : index + MAX_TELEGRAM_MESSAGE_LENGTH]
        for index in range(0, len(text), MAX_TELEGRAM_MESSAGE_LENGTH)
    ] or [""]


def keep_recent_pending_updates(limit: int) -> None:
    if limit < 1:
        return

    params = urllib.parse.urlencode({"offset": -limit, "limit": limit, "timeout": 0})
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning("Failed to trim pending Telegram updates: %s", exc)
        return

    if not data.get("ok"):
        logger.warning("Telegram getUpdates returned an error while trimming pending updates: %s", data)
        return

    pending_count = len(data.get("result") or [])
    logger.info("Kept up to %s pending Telegram updates on startup; current batch=%s", limit, pending_count)


def bot_usernames(context: ContextTypes.DEFAULT_TYPE) -> set[str]:
    usernames = set(TELEGRAM_BOT_USERNAMES)
    runtime_username = getattr(context.bot, "username", None)
    if runtime_username:
        usernames.add(runtime_username.lstrip("@").lower())
    return {username for username in usernames if username}


def mention_prefixes(usernames: set[str]) -> list[str]:
    return [f"@{username}" for username in sorted(usernames)]


def text_without_bot_mentions(text: str, usernames: set[str]) -> tuple[str, bool]:
    prompt = text
    mentioned = False
    for username in usernames:
        pattern = re.compile(rf"@{re.escape(username)}\b", re.IGNORECASE)
        if pattern.search(prompt):
            mentioned = True
            prompt = pattern.sub("", prompt)
    return prompt.strip(" \t\n\r,:"), mentioned


def prompt_from_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    text = (update.message.text or "").strip()
    if update.effective_chat.type == ChatType.PRIVATE:
        logger.info("Update prefix check: chat_type=%s prefixes=%s private_chat=True", update.effective_chat.type, mention_prefixes(bot_usernames(context)))
        return text

    usernames = bot_usernames(context)
    prefixes = mention_prefixes(usernames)
    prompt, mentioned = text_without_bot_mentions(text, usernames)
    logger.info(
        "Update prefix check: chat_type=%s prefixes=%s mentioned=%s text=%r prompt=%r",
        update.effective_chat.type,
        prefixes,
        mentioned,
        text,
        prompt,
    )
    if mentioned:
        return prompt

    reply_to = update.message.reply_to_message
    if reply_to and reply_to.from_user and reply_to.from_user.id == context.bot.id:
        return text

    return ""


def is_allowed_user(update: Update) -> bool:
    allowed_user_ids = allowed_telegram_user_ids()
    if not allowed_user_ids:
        return True

    user = update.effective_user
    return bool(user and str(user.id) in allowed_user_ids)


def allowed_telegram_user_ids() -> set[str]:
    allowed_user_ids = set(ALLOWED_TELEGRAM_USER_IDS_FROM_ENV)
    try:
        for line in ALLOWED_TELEGRAM_USER_IDS_FILE.read_text(encoding="utf-8").splitlines():
            user_id = line.split("#", 1)[0].strip()
            if user_id:
                allowed_user_ids.add(user_id)
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.warning("Failed to read allowed Telegram user IDs from %s: %s", ALLOWED_TELEGRAM_USER_IDS_FILE, exc)
    return allowed_user_ids


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    await update.message.reply_text("프롬프트를 보내면 Gemma4 Ollama 서버에 전달하고 답변을 회신합니다.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    await update.message.reply_text(
        "사용법:\n"
        "1. 이 채팅창에 질문이나 프롬프트를 입력합니다.\n"
        "2. 봇이 Gemma4 서버의 /api/generate로 전송합니다.\n"
        "3. 생성된 답변을 다시 전달합니다."
    )


async def handle_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed_user(update):
        user = update.effective_user
        logger.info(
            "Ignored message from unauthorized user: user_id=%s username=%s",
            getattr(user, "id", None),
            getattr(user, "username", None),
        )
        return

    prompt = prompt_from_update(update, context)
    if not prompt:
        if update.effective_chat.type == ChatType.PRIVATE:
            await update.message.reply_text("프롬프트를 입력해 주세요.")
        return

    await update.message.reply_text("thinking...")
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

    keep_recent_pending_updates(MAX_PENDING_UPDATES_ON_STARTUP)
    logger.info(
        "Telegram bot started. LLM_API_URL=%s prefixes=%s allowed_user_ids_file=%s allowed_user_count=%s",
        LLM_API_URL,
        mention_prefixes(TELEGRAM_BOT_USERNAMES),
        ALLOWED_TELEGRAM_USER_IDS_FILE,
        len(allowed_telegram_user_ids()),
    )
    application.run_polling()


if __name__ == "__main__":
    main()
