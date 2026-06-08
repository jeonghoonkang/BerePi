import asyncio
import ast
import base64
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

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
LLM_ENQUEUE_URL = os.environ.get(
    "LLM_ENQUEUE_URL",
    urllib.parse.urljoin(LLM_API_URL, "/api/enqueue-generate"),
)
LLM_PROMPT_RESULT_URL = os.environ.get(
    "LLM_PROMPT_RESULT_URL",
    urllib.parse.urljoin(LLM_API_URL, "/api/prompt-result"),
)
LLM_STATUS_URL = os.environ.get(
    "LLM_STATUS_URL",
    urllib.parse.urljoin(LLM_API_URL, "/api/status"),
)
PROMPT_RESULT_POLL_INTERVAL_SECONDS = float(os.environ.get("PROMPT_RESULT_POLL_INTERVAL_SECONDS", "1"))
GEMMA4_USER_ID = os.environ.get("GEMMA4_USER_ID", "").strip()
GEMMA4_PASSWORD = os.environ.get("GEMMA4_PASSWORD", "")
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "180"))
PROMPT_RESULT_TIMEOUT_SECONDS = int(os.environ.get("PROMPT_RESULT_TIMEOUT_SECONDS", str(REQUEST_TIMEOUT + 60)))
MAX_TELEGRAM_MESSAGE_LENGTH = 4096
MAX_PENDING_UPDATES_ON_STARTUP = int(os.environ.get("MAX_PENDING_UPDATES_ON_STARTUP", "10"))
DEFAULT_IMAGE_PROMPT = os.environ.get("DEFAULT_IMAGE_PROMPT", "Describe this image.")
LLM_MODEL = os.environ.get("LLM_MODEL", os.environ.get("OLLAMA_MODEL", "")).strip()
ENABLE_MODEL_PLOT_CODE_EXECUTION = os.environ.get("ENABLE_MODEL_PLOT_CODE_EXECUTION", "1").strip().lower() not in {"0", "false", "no"}
MODEL_PLOT_CODE_TIMEOUT_SECONDS = int(os.environ.get("MODEL_PLOT_CODE_TIMEOUT_SECONDS", "15"))
MAX_MODEL_PLOT_CODE_BLOCKS = int(os.environ.get("MAX_MODEL_PLOT_CODE_BLOCKS", "2"))
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


def encode_image_base64(image_path: Path) -> str:
    return base64.b64encode(image_path.read_bytes()).decode("ascii")


def prompt_payload(prompt: str, images: Optional[list[str]] = None) -> dict:
    payload = {"prompt": prompt, "prompts": [prompt], "stream": False}
    if LLM_MODEL:
        payload["model"] = LLM_MODEL
    if images:
        payload["images"] = images
    if GEMMA4_USER_ID or GEMMA4_PASSWORD:
        payload["user_id"] = GEMMA4_USER_ID
        payload["password"] = GEMMA4_PASSWORD
    return payload


def post_json(url: str, payload: dict, timeout: int = REQUEST_TIMEOUT) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API 오류({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"API 서버에 연결할 수 없습니다: {exc.reason}") from exc


def get_json(url: str, timeout: int = 30) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API 오류({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"API 서버에 연결할 수 없습니다: {exc.reason}") from exc


def enqueue_llm_prompt(prompt: str, images: Optional[list[str]] = None) -> dict:
    return post_json(LLM_ENQUEUE_URL, prompt_payload(prompt, images))


def prompt_result_url(job_id: int) -> str:
    return f"{LLM_PROMPT_RESULT_URL}?{urllib.parse.urlencode({'id': job_id})}"


def fetch_prompt_result(job_id: int) -> dict:
    return get_json(prompt_result_url(job_id))


async def wait_for_prompt_result(job_id: int) -> dict:
    deadline = asyncio.get_running_loop().time() + PROMPT_RESULT_TIMEOUT_SECONDS
    while True:
        data = fetch_prompt_result(job_id)
        if data.get("done"):
            if data.get("error"):
                raise RuntimeError(str(data.get("error")))
            return data
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError(f"prompt job {job_id} did not finish within {PROMPT_RESULT_TIMEOUT_SECONDS}s")
        await asyncio.sleep(PROMPT_RESULT_POLL_INTERVAL_SECONDS)


def queue_line_from_response(data: dict) -> str:
    queue_line_value = str(data.get("queue_line") or "").strip()
    if queue_line_value:
        return queue_line_value
    job_id = data.get("prompt_queue_id", "unknown")
    prompts_ahead = int_or_zero(data.get("prompts_ahead_on_enqueue"))
    estimated_wait = float_or_zero(data.get("estimated_wait_seconds_on_enqueue"))
    queue_wait = float_or_zero(data.get("queue_wait_seconds"))
    pending = int_or_zero(data.get("pending_prompt_count_on_enqueue"))
    return (
        f"Queue: Queue ID: {job_id} | "
        f"Prompts ahead: {prompts_ahead} | "
        f"Estimated wait: {estimated_wait:.2f}s | "
        f"Queue wait: {queue_wait:.2f}s | "
        f"Pending on enqueue: {pending}"
    )


def call_llm_api(prompt: str, images: Optional[list[str]] = None) -> str:
    return format_llm_response(post_json(LLM_API_URL, prompt_payload(prompt, images)))


def initial_thinking_message() -> str:
    return f"thinking...\n{initial_queue_line()}"


def initial_queue_line() -> str:
    try:
        with urllib.request.urlopen(LLM_STATUS_URL, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to fetch prompt queue status from %s: %s", LLM_STATUS_URL, exc)
        return queue_line(prompts_ahead=0, estimated_wait_seconds=0.0, queue_wait_seconds=0.0, pending_on_enqueue=1)

    queue = data.get("prompt_queue") if isinstance(data, dict) else {}
    if not isinstance(queue, dict):
        queue = {}

    pending_count = int_or_zero(queue.get("pending_count"))
    active_count = 1 if queue.get("active") else 0
    prompts_ahead = pending_count + active_count
    estimated_wait_seconds = float_or_zero(queue.get("estimated_wait_seconds"))
    pending_on_enqueue = pending_count + 1

    return queue_line(
        prompts_ahead=prompts_ahead,
        estimated_wait_seconds=estimated_wait_seconds,
        queue_wait_seconds=0.0,
        pending_on_enqueue=pending_on_enqueue,
    )


def queue_line(
    *,
    prompts_ahead: int,
    estimated_wait_seconds: float,
    queue_wait_seconds: float,
    pending_on_enqueue: int,
) -> str:
    return (
        f"Prompts ahead: {prompts_ahead} | "
        f"Estimated wait: {estimated_wait_seconds:.2f}s | "
        f"Queue wait: {queue_wait_seconds:.2f}s | "
        f"Pending on enqueue: {pending_on_enqueue}"
    )


def int_or_zero(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def float_or_zero(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def format_llm_response(data: dict) -> str:
    visible_response = str(data.get("visible_response") or data.get("answer") or "").strip()
    raw_response = str(data.get("response") or "").strip()
    thinking = str(data.get("thinking") or "").strip()
    answer = visible_response or raw_response

    if not answer and thinking:
        answer = thinking
    if not answer:
        raise RuntimeError(f"API 응답에 response가 없습니다: {data}")

    lines = [answer]

    info_lines = response_info_lines(data)
    if info_lines:
        lines.append("[정보]\n" + "\n".join(info_lines))

    if thinking and visible_response and thinking != visible_response:
        lines.append("[Thinking]\n" + thinking)

    return "\n\n".join(lines)


def response_info_lines(data: dict) -> list[str]:
    info: list[str] = []
    elapsed_line = str(data.get("elapsed_line") or "").strip()
    if elapsed_line:
        info.append(elapsed_line)
    else:
        elapsed_seconds = data.get("elapsed_seconds")
        model = data.get("model")
        server_ip = data.get("server_ip")
        server_port = data.get("server_port")
        parts = []
        if elapsed_seconds is not None:
            try:
                parts.append(f"Elapsed time: {float(elapsed_seconds):.2f}s")
            except (TypeError, ValueError):
                parts.append(f"Elapsed time: {elapsed_seconds}s")
        if model:
            parts.append(f"Model: {model}")
        if server_ip:
            parts.append(f"IP: {server_ip}")
        if server_port:
            parts.append(f"Port: {server_port}")
        if parts:
            info.append(" | ".join(parts))

    queue_parts = []
    for key, label in (
        ("prompt_queue_id", "Queue ID"),
        ("prompts_ahead_on_enqueue", "Prompts ahead"),
        ("estimated_wait_seconds_on_enqueue", "Estimated wait"),
        ("queue_wait_seconds", "Queue wait"),
        ("pending_prompt_count_on_enqueue", "Pending on enqueue"),
    ):
        value = data.get(key)
        if value is None:
            continue
        if key.endswith("seconds_on_enqueue") or key == "queue_wait_seconds":
            try:
                value = f"{float(value):.2f}s"
            except (TypeError, ValueError):
                value = f"{value}s"
        queue_parts.append(f"{label}: {value}")
    if queue_parts:
        info.append("Queue: " + " | ".join(queue_parts))

    image_count = data.get("image_count")
    if image_count:
        info.append(f"Images: {image_count}")

    return info


def split_message(text: str) -> list[str]:
    return [
        text[index : index + MAX_TELEGRAM_MESSAGE_LENGTH]
        for index in range(0, len(text), MAX_TELEGRAM_MESSAGE_LENGTH)
    ] or [""]


def extract_python_code_blocks(text: str) -> list[str]:
    return [
        match.group(1).strip()
        for match in re.finditer(r"```(?:python|py)\s*\n(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
        if match.group(1).strip()
    ]


def is_model_plot_code_candidate(code: str) -> bool:
    lowered = code.lower()
    if "matplotlib" in lowered or "plt." in lowered:
        return True

    words = set(re.findall(r"[a-z0-9_]+", lowered))
    plot_words = {"plot", "plots", "plotting", "boxplot"}
    yolo_box_words = {"yolo", "box", "boxes", "bbox", "bboxes", "bounding"}
    return bool(words & plot_words) and bool(words & yolo_box_words)


def sanitized_plot_code(code: str) -> str:
    lines: list[str] = []
    for line in code.splitlines():
        stripped = line.strip()
        if stripped in {"import matplotlib.pyplot as plt", "from matplotlib import pyplot as plt"}:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def validate_plot_code(code: str) -> None:
    allowed_nodes = (
        ast.Module,
        ast.Import,
        ast.ImportFrom,
        ast.alias,
        ast.Assign,
        ast.AnnAssign,
        ast.Expr,
        ast.Call,
        ast.Attribute,
        ast.Name,
        ast.Load,
        ast.Store,
        ast.Constant,
        ast.List,
        ast.Tuple,
        ast.Dict,
        ast.keyword,
        ast.Subscript,
        ast.Slice,
        ast.BinOp,
        ast.UnaryOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Mod,
        ast.Pow,
        ast.USub,
        ast.UAdd,
    )
    allowed_builtins = {"dict", "list", "tuple", "range", "len", "min", "max", "sum", "sorted", "abs", "round"}
    allowed_pyplot_calls = {
        "figure",
        "subplot",
        "subplots",
        "plot",
        "scatter",
        "bar",
        "barh",
        "hist",
        "boxplot",
        "title",
        "suptitle",
        "xlabel",
        "ylabel",
        "xticks",
        "yticks",
        "xlim",
        "ylim",
        "grid",
        "legend",
        "tight_layout",
        "show",
    }

    tree = ast.parse(code)
    for node in ast.walk(tree):
        if not isinstance(node, allowed_nodes):
            raise ValueError(f"unsupported plot code syntax: {type(node).__name__}")
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name != "matplotlib.pyplot" or alias.asname != "plt":
                    raise ValueError("only 'import matplotlib.pyplot as plt' is allowed")
        elif isinstance(node, ast.ImportFrom):
            if node.module != "matplotlib":
                raise ValueError("only 'from matplotlib import pyplot as plt' is allowed")
            if len(node.names) != 1 or node.names[0].name != "pyplot" or node.names[0].asname != "plt":
                raise ValueError("only 'from matplotlib import pyplot as plt' is allowed")
        elif isinstance(node, ast.Name) and node.id.startswith("_"):
            raise ValueError("private names are not allowed in plot code")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise ValueError("private attributes are not allowed in plot code")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                if func.id not in allowed_builtins:
                    raise ValueError(f"function is not allowed in plot code: {func.id}")
            elif isinstance(func, ast.Attribute):
                if not isinstance(func.value, ast.Name) or func.value.id != "plt" or func.attr not in allowed_pyplot_calls:
                    raise ValueError("only selected matplotlib.pyplot calls are allowed")
            else:
                raise ValueError("unsupported function call in plot code")


def render_plot_code_block(code: str) -> list[Path]:
    safe_code = sanitized_plot_code(code)
    validate_plot_code(code)
    validate_plot_code(safe_code)

    work_dir = Path(tempfile.mkdtemp(prefix="telegram_model_plot_"))
    code_path = work_dir / "plot_code.py"
    code_path.write_text(safe_code, encoding="utf-8")
    runner_path = work_dir / "render_plot.py"
    runner_path.write_text(
        "\n".join(
            [
                "import json",
                "from pathlib import Path",
                "import matplotlib",
                "matplotlib.use('Agg')",
                "import matplotlib.pyplot as plt",
                "work_dir = Path(__file__).resolve().parent",
                "code = (work_dir / 'plot_code.py').read_text(encoding='utf-8')",
                "safe_builtins = {",
                "    'dict': dict, 'list': list, 'tuple': tuple, 'range': range, 'len': len,",
                "    'min': min, 'max': max, 'sum': sum, 'sorted': sorted, 'abs': abs, 'round': round,",
                "}",
                "plt.show = lambda *args, **kwargs: None",
                "exec(compile(code, 'plot_code.py', 'exec'), {'__builtins__': safe_builtins, 'plt': plt}, {})",
                "paths = []",
                "for index, fig_num in enumerate(plt.get_fignums(), start=1):",
                "    out_path = work_dir / f'model_plot_{index}.png'",
                "    plt.figure(fig_num).savefig(out_path, bbox_inches='tight')",
                "    paths.append(str(out_path))",
                "print(json.dumps(paths))",
            ]
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["MPLBACKEND"] = "Agg"
    try:
        result = subprocess.run(
            [sys.executable, str(runner_path)],
            cwd=str(work_dir),
            env=env,
            text=True,
            capture_output=True,
            timeout=max(1, MODEL_PLOT_CODE_TIMEOUT_SECONDS),
            check=True,
        )
        paths = [Path(path) for path in json.loads(result.stdout or "[]")]
        if not paths:
            shutil.rmtree(work_dir, ignore_errors=True)
        return paths
    except Exception:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise


def render_model_plot_images(answer: str) -> list[Path]:
    if not ENABLE_MODEL_PLOT_CODE_EXECUTION:
        return []

    plot_paths: list[Path] = []
    for code in extract_python_code_blocks(answer)[: max(0, MAX_MODEL_PLOT_CODE_BLOCKS)]:
        if not is_model_plot_code_candidate(code):
            continue
        try:
            plot_paths.extend(render_plot_code_block(code))
        except Exception as exc:
            logger.warning("Failed to render model plot code block: %s", exc)
    return plot_paths


def cleanup_generated_plot_images(paths: list[Path]) -> None:
    seen_dirs: set[Path] = set()
    for path in paths:
        seen_dirs.add(path.parent)
    for directory in seen_dirs:
        if directory.name.startswith("telegram_model_plot_"):
            shutil.rmtree(directory, ignore_errors=True)


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


def message_text(update: Update) -> str:
    return ((update.message.text or update.message.caption or "") if update.message else "").strip()


def message_has_photo(update: Update) -> bool:
    return image_attachment_from_update(update) is not None


def message_mentions_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    _, mentioned = text_without_bot_mentions(message_text(update), bot_usernames(context))
    return mentioned


def should_use_default_image_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if update.effective_chat.type == ChatType.PRIVATE:
        return True
    return message_mentions_bot(update, context)


def image_attachment_from_message(message):
    if not message:
        return None
    if message.photo:
        return message.photo[-1]
    document = message.document
    if document and str(document.mime_type or "").startswith("image/"):
        return document
    return None


def image_attachment_from_update(update: Update):
    if not update.message:
        return None
    current_image = image_attachment_from_message(update.message)
    if current_image:
        return current_image
    return image_attachment_from_message(update.message.reply_to_message)


def image_attachment_source(update: Update) -> str:
    if not update.message:
        return "none"
    if image_attachment_from_message(update.message):
        return "message"
    if image_attachment_from_message(update.message.reply_to_message):
        return "reply_to_message"
    return "none"


async def image_base64s_from_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> list[str]:
    del context
    image_attachment = image_attachment_from_update(update)
    if not image_attachment:
        logger.info("No Telegram image attachment found for model payload")
        return []

    telegram_file = await image_attachment.get_file()
    suffix = Path(str(telegram_file.file_path or "")).suffix or ".jpg"
    image_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(prefix="telegram_photo_", suffix=suffix, delete=False) as image_file:
            image_path = Path(image_file.name)
        await telegram_file.download_to_drive(custom_path=image_path)
        logger.info("Encoded Telegram image from %s for model payload", image_attachment_source(update))
        return [encode_image_base64(image_path)]
    finally:
        if image_path is not None:
            try:
                image_path.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("Failed to remove temporary Telegram image %s: %s", image_path, exc)


def prompt_from_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    text = message_text(update)
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
        "2. 봇이 Gemma4 서버의 /api/enqueue-generate로 전송합니다.\n"
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
    has_photo = message_has_photo(update)
    if not prompt and has_photo and should_use_default_image_prompt(update, context):
        prompt = DEFAULT_IMAGE_PROMPT
    if not prompt:
        if update.effective_chat.type == ChatType.PRIVATE:
            await update.message.reply_text("프롬프트를 입력해 주세요.")
        return

    thinking_message = None
    try:
        images = await image_base64s_from_update(update, context) if has_photo else []
        if has_photo:
            logger.info("Sending prompt to LLM with image_count=%s", len(images))
        enqueue_response = enqueue_llm_prompt(prompt, images)
        thinking_message = await update.message.reply_text(f"thinking...\n{queue_line_from_response(enqueue_response)}")
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        job_id = int(enqueue_response.get("prompt_queue_id"))
        result = await wait_for_prompt_result(job_id)
        answer = format_llm_response(result)
    except Exception as exc:
        logger.exception("Failed to handle prompt")
        message = f"오류가 발생했습니다.\n{exc}"
        if thinking_message:
            await thinking_message.edit_text(message)
        else:
            await update.message.reply_text(message)
        return

    chunks = split_message(answer)
    await thinking_message.edit_text(chunks[0])
    for chunk in chunks[1:]:
        await update.message.reply_text(chunk)

    plot_paths = await asyncio.to_thread(render_model_plot_images, answer)
    try:
        for index, plot_path in enumerate(plot_paths, start=1):
            with plot_path.open("rb") as photo:
                await update.message.reply_photo(photo=photo, caption=f"Generated plot {index}")
    finally:
        cleanup_generated_plot_images(plot_paths)


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN 환경 변수를 설정하세요.")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler((filters.TEXT | filters.PHOTO | filters.Document.IMAGE) & ~filters.COMMAND, handle_prompt))

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
