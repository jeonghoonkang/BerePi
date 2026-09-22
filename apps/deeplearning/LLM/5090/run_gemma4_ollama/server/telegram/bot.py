from __future__ import annotations

import asyncio
import ast
import base64
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

from telegram import Update
from telegram.constants import ChatAction, ChatType
from telegram.error import RetryAfter
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
WRITING_TECH_DOC_TOOL_URL = os.environ.get(
    "WRITING_TECH_DOC_TOOL_URL",
    urllib.parse.urljoin(LLM_API_URL, "/api/tools/writing-tech-doc"),
)
WRITING_TECH_DOC_TOOL_TIMEOUT = int(os.environ.get("WRITING_TECH_DOC_TOOL_TIMEOUT", "960"))
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


def prompt_payload(prompt: str, images: Optional[list[str]] = None, identity: Optional[dict] = None) -> dict:
    payload = {"prompt": prompt, "prompts": [prompt], "stream": False}
    if LLM_MODEL:
        payload["model"] = LLM_MODEL
    if images:
        payload["images"] = images
    if GEMMA4_USER_ID or GEMMA4_PASSWORD:
        payload["user_id"] = GEMMA4_USER_ID
        payload["password"] = GEMMA4_PASSWORD
    payload.update(identity or {})
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


def writing_tool_payload(tool: str, **arguments: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"tool": tool, "arguments": arguments}
    if GEMMA4_USER_ID or GEMMA4_PASSWORD:
        payload["user_id"] = GEMMA4_USER_ID
        payload["password"] = GEMMA4_PASSWORD
    return payload


def call_writing_tool(tool: str, **arguments: Any) -> dict:
    return post_json(
        WRITING_TECH_DOC_TOOL_URL,
        writing_tool_payload(tool, **arguments),
        timeout=WRITING_TECH_DOC_TOOL_TIMEOUT,
    )


def writing_tool_result_text(result: dict) -> str:
    tool = str(result.get("tool") or "tool")
    elapsed = result.get("elapsed_seconds")
    heading = f"[{tool} 완료]"
    if elapsed is not None:
        heading += f" {elapsed}초"
    sections = [heading]
    stdout = str(result.get("stdout") or "").strip()
    stderr = str(result.get("stderr") or "").strip()
    if stdout:
        sections.append(stdout)
    if stderr:
        sections.append("[stderr]\n" + stderr)
    if result.get("output_truncated"):
        sections.append("[안내] 서버 출력 길이 제한으로 일부 결과가 생략되었습니다.")
    return "\n\n".join(sections)


def enqueue_llm_prompt(prompt: str, images: Optional[list[str]] = None, identity: Optional[dict] = None) -> dict:
    return post_json(LLM_ENQUEUE_URL, prompt_payload(prompt, images, identity))


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


def compact_telegram_summary_text(value: object, limit: int = 80) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def telegram_response_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    chat = update.effective_chat
    if chat is None:
        return ""

    chat_type = getattr(chat, "type", "") or "unknown"
    chat_type_label = {
        ChatType.PRIVATE: "개인 대화",
        ChatType.GROUP: "그룹",
        ChatType.SUPERGROUP: "슈퍼그룹",
        ChatType.CHANNEL: "채널",
    }.get(chat_type, str(chat_type))
    title = compact_telegram_summary_text(getattr(chat, "title", ""))
    chat_description = f"{chat_type_label} ({title})" if title else chat_type_label

    message = update.effective_message
    topic_id = getattr(message, "message_thread_id", None) if message else None
    room_id = f"{getattr(chat, 'id', 'unknown')}:{topic_id or 0}"

    parts = [f"Chat: {chat_description}", f"Room ID: {room_id}"]
    bot_username = compact_telegram_summary_text(getattr(context.bot, "username", "")).lstrip("@")
    if bot_username:
        parts.append(f"Bot: @{bot_username}")
    return " | ".join(parts)


def append_telegram_response_summary(
    answer: str, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> str:
    summary = telegram_response_summary(update, context)
    if not summary:
        return answer
    return f"{answer.rstrip()}\n\n[Telegram]\n{summary}"


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
        if stripped in {
            "import matplotlib.pyplot as plt",
            "from matplotlib import pyplot as plt",
            "import matplotlib.patches as patches",
            "import matplotlib.patches as mpatches",
            "from matplotlib.patches import Rectangle",
            "from matplotlib.patches import Rectangle as Rectangle",
        }:
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
        ast.For,
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
        ast.JoinedStr,
        ast.FormattedValue,
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
        "gca",
        "imshow",
        "text",
        "axis",
        "legend",
        "tight_layout",
        "show",
    }
    allowed_axes_calls = {
        "add_patch",
        "imshow",
        "text",
        "axis",
        "set_xlim",
        "set_ylim",
        "set_title",
        "set_xlabel",
        "set_ylabel",
        "invert_yaxis",
    }

    tree = ast.parse(code)
    for node in ast.walk(tree):
        if not isinstance(node, allowed_nodes):
            raise ValueError(f"unsupported plot code syntax: {type(node).__name__}")
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "matplotlib.pyplot" and alias.asname == "plt":
                    continue
                if alias.name == "matplotlib.patches" and alias.asname in {"patches", "mpatches"}:
                    continue
                raise ValueError(
                    "only 'import matplotlib.pyplot as plt' or "
                    "'import matplotlib.patches as patches' is allowed"
                )
        elif isinstance(node, ast.ImportFrom):
            if node.module == "matplotlib":
                if len(node.names) == 1 and node.names[0].name == "pyplot" and node.names[0].asname == "plt":
                    continue
            elif node.module == "matplotlib.patches":
                if len(node.names) == 1 and node.names[0].name == "Rectangle" and node.names[0].asname in {None, "Rectangle"}:
                    continue
            raise ValueError(
                "only 'from matplotlib import pyplot as plt' or "
                "'from matplotlib.patches import Rectangle' is allowed"
            )
        elif isinstance(node, ast.Name) and node.id.startswith("_"):
            raise ValueError("private names are not allowed in plot code")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise ValueError("private attributes are not allowed in plot code")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                if func.id not in allowed_builtins and func.id != "Rectangle":
                    raise ValueError(f"function is not allowed in plot code: {func.id}")
            elif isinstance(func, ast.Attribute):
                if isinstance(func.value, ast.Name):
                    if func.value.id == "plt" and func.attr in allowed_pyplot_calls:
                        continue
                    if func.value.id in {"patches", "mpatches"} and func.attr == "Rectangle":
                        continue
                if func.attr in allowed_axes_calls:
                    continue
                raise ValueError("only selected matplotlib plotting calls are allowed")
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
                "import matplotlib.patches as patches",
                "mpatches = patches",
                "from matplotlib.patches import Rectangle",
                "work_dir = Path(__file__).resolve().parent",
                "code = (work_dir / 'plot_code.py').read_text(encoding='utf-8')",
                "safe_builtins = {",
                "    'dict': dict, 'list': list, 'tuple': tuple, 'range': range, 'len': len,",
                "    'min': min, 'max': max, 'sum': sum, 'sorted': sorted, 'abs': abs, 'round': round,",
                "}",
                "plt.show = lambda *args, **kwargs: None",
                "exec_globals = {",
                "    '__builtins__': safe_builtins, 'plt': plt,",
                "    'patches': patches, 'mpatches': mpatches, 'Rectangle': Rectangle,",
                "}",
                "exec(compile(code, 'plot_code.py', 'exec'), exec_globals, {})",
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


def extract_json_object(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    for pattern in (
        r"```(?:json)?\s*\n(.*?)```",
        r"```\s*\n(.*?)```",
    ):
        for match in re.finditer(pattern, candidate, flags=re.IGNORECASE | re.DOTALL):
            parsed = parse_json_object(match.group(1))
            if parsed is not None:
                return parsed
    return parse_json_object(candidate)


def parse_json_object(candidate: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(candidate[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None


# Mirrors server.py's YOLO Detection tab: normalized bbox JSON over the uploaded image.
def normalized_detection_box(box: object) -> dict[str, float] | None:
    if not isinstance(box, dict):
        return None
    try:
        x = float(box.get("x"))
        y = float(box.get("y"))
        width = float(box.get("width", box.get("w")))
        height = float(box.get("height", box.get("h")))
    except (TypeError, ValueError):
        return None
    if not all(value == value and value not in {float("inf"), float("-inf")} for value in (x, y, width, height)):
        return None
    return {
        "x": max(0.0, min(1.0, x)),
        "y": max(0.0, min(1.0, y)),
        "width": max(0.0, min(1.0, width)),
        "height": max(0.0, min(1.0, height)),
    }


def collect_detection_objects(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    raw_objects = data.get("objects")
    if not isinstance(raw_objects, list):
        raw_objects = data.get("detections")
    if not isinstance(raw_objects, list):
        return []

    objects: list[dict[str, Any]] = []
    for item in raw_objects:
        if not isinstance(item, dict):
            continue
        bbox = normalized_detection_box(item.get("bbox") or item.get("box"))
        if bbox:
            objects.append({**item, "bbox": bbox})
    return objects


def detection_label(item: dict[str, Any]) -> str:
    label = str(item.get("label") or item.get("class") or "object")
    confidence = item.get("confidence", item.get("score"))
    try:
        return f"{label} {float(confidence):.2f}" if confidence is not None else label
    except (TypeError, ValueError):
        return label


def render_detection_box_image(image_path: Path, response_text: str) -> list[Path]:
    objects = collect_detection_objects(extract_json_object(response_text))
    if not objects:
        return []

    from PIL import Image, ImageDraw, ImageFont

    work_dir = Path(tempfile.mkdtemp(prefix="telegram_yolo_detection_"))
    try:
        with Image.open(image_path) as source_image:
            image = source_image.convert("RGB")

        max_width = 1000
        scale = min(1.0, max_width / max(1, image.width))
        width = max(1, round(image.width * scale))
        height = max(1, round(image.height * scale))
        if (width, height) != image.size:
            image = image.resize((width, height))

        draw = ImageDraw.Draw(image)
        line_width = max(2, round(width / 320))
        font_size = max(13, round(width / 52))
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()

        colors = ["#137c5b", "#a62f2f", "#255f99", "#9b5a00", "#6d4ca3"]
        for index, item in enumerate(objects):
            color = colors[index % len(colors)]
            box = item["bbox"]
            x = box["x"] * width
            y = box["y"] * height
            box_width = box["width"] * width
            box_height = box["height"] * height
            label = detection_label(item)

            draw.rectangle((x, y, x + box_width, y + box_height), outline=color, width=line_width)
            text_bbox = draw.textbbox((0, 0), label, font=font)
            text_width = min(text_bbox[2] - text_bbox[0] + 10, max(1, width - round(x)))
            text_height = max(20, round(width / 36))
            label_y = max(0, round(y) - text_height)
            draw.rectangle((x, label_y, x + text_width, label_y + text_height), fill=color)
            draw.text((x + 5, label_y + 3), label, fill="#ffffff", font=font)

        out_path = work_dir / "yolo_detection_boxes.png"
        image.save(out_path)
        return [out_path]
    except Exception:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise


def render_detection_box_images(image_paths: list[Path], response_text: str) -> list[Path]:
    if not image_paths:
        return []
    try:
        return render_detection_box_image(image_paths[0], response_text)
    except Exception as exc:
        logger.warning("Failed to render YOLO detection boxes from model response: %s", exc)
        return []


def cleanup_generated_plot_images(paths: list[Path]) -> None:
    seen_dirs: set[Path] = set()
    for path in paths:
        seen_dirs.add(path.parent)
    for directory in seen_dirs:
        if directory.name.startswith(("telegram_model_plot_", "telegram_yolo_detection_")):
            shutil.rmtree(directory, ignore_errors=True)


def cleanup_temp_image_paths(paths: list[Path]) -> None:
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Failed to remove temporary Telegram image %s: %s", path, exc)


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


async def image_payloads_from_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> tuple[list[str], list[Path]]:
    del context
    image_attachment = image_attachment_from_update(update)
    if not image_attachment:
        logger.info("No Telegram image attachment found for model payload")
        return [], []

    telegram_file = await image_attachment.get_file()
    suffix = Path(str(telegram_file.file_path or "")).suffix or ".jpg"
    image_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(prefix="telegram_photo_", suffix=suffix, delete=False) as image_file:
            image_path = Path(image_file.name)
        await telegram_file.download_to_drive(custom_path=image_path)
        logger.info("Encoded Telegram image from %s for model payload", image_attachment_source(update))
        return [encode_image_base64(image_path)], [image_path]
    except Exception:
        if image_path is not None:
            cleanup_temp_image_paths([image_path])
        raise


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


def command_argument_text(update: Update) -> str:
    text = message_text(update)
    parts = text.split(maxsplit=1)
    return parts[1].strip() if len(parts) == 2 else ""


def parse_boost_command(arguments: str) -> dict[str, Any]:
    try:
        tokens = shlex.split(arguments)
    except ValueError as exc:
        raise ValueError(f"boost 인자를 해석할 수 없습니다: {exc}") from exc
    dry_run = False
    filename_parts: list[str] = []
    for token in tokens:
        if token == "--dry-run":
            dry_run = True
        elif token.startswith("--"):
            raise ValueError(f"지원하지 않는 boost 옵션입니다: {token}")
        else:
            filename_parts.append(token)
    payload: dict[str, Any] = {"dry_run": dry_run}
    if filename_parts:
        payload["file"] = " ".join(filename_parts)
    return payload


def parse_findm_command(arguments: str) -> dict[str, Any]:
    try:
        tokens = shlex.split(arguments)
    except ValueError as exc:
        raise ValueError(f"findm 인자를 해석할 수 없습니다: {exc}") from exc
    query_parts: list[str] = []
    page_size: int | None = None
    filters: dict[str, str] = {}
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "--page-size":
            index += 1
            if index >= len(tokens):
                raise ValueError("--page-size 뒤에 숫자를 입력해 주세요.")
            try:
                page_size = int(tokens[index])
            except ValueError as exc:
                raise ValueError("--page-size는 숫자여야 합니다.") from exc
        elif token.startswith("--page-size="):
            try:
                page_size = int(token.split("=", 1)[1])
            except ValueError as exc:
                raise ValueError("--page-size는 숫자여야 합니다.") from exc
        elif token in {"--author", "--room", "--topic"}:
            index += 1
            if index >= len(tokens) or not tokens[index]:
                raise ValueError(f"{token} 뒤에 ID를 입력해 주세요.")
            filters[token.removeprefix("--")] = tokens[index]
        elif any(token.startswith(option + "=") for option in ("--author", "--room", "--topic")):
            option, value = token.split("=", 1)
            if not value:
                raise ValueError(f"{option} 뒤에 ID를 입력해 주세요.")
            filters[option.removeprefix("--")] = value
        elif token.startswith("--"):
            raise ValueError(f"지원하지 않는 findm 옵션입니다: {token}")
        else:
            query_parts.append(token)
        index += 1
    if not query_parts:
        raise ValueError("검색어를 입력해 주세요. 예: /findm 서버 연동")
    payload = {"query": " ".join(query_parts)}
    if page_size is not None:
        payload["page_size"] = page_size
    payload.update(filters)
    return payload


def telegram_allom_identity(update: Update) -> dict[str, str]:
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message
    if chat is None or user is None or message is None:
        raise ValueError("Telegram 채팅방 또는 작성자 정보를 확인할 수 없습니다.")

    username = compact_telegram_summary_text(getattr(user, "username", "")).lstrip("@")
    if username:
        author_name = f"@{username}"
    else:
        author_name = compact_telegram_summary_text(
            " ".join(
                part for part in (getattr(user, "first_name", ""), getattr(user, "last_name", "")) if part
            )
        )
    identity = {
        "room": str(chat.id),
        "topic": str(getattr(message, "message_thread_id", None) or 0),
        "author": str(user.id),
    }
    if author_name:
        identity["author_name"] = author_name
    return identity


async def execute_writing_tool(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    tool: str,
    arguments: dict[str, Any],
) -> None:
    if not is_allowed_user(update):
        user = update.effective_user
        logger.info(
            "Ignored tool command from unauthorized user: tool=%s user_id=%s username=%s",
            tool,
            getattr(user, "id", None),
            getattr(user, "username", None),
        )
        return
    progress = await update.message.reply_text(f"{tool} 실행 중...")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    try:
        result = await asyncio.to_thread(call_writing_tool, tool, **arguments)
        chunks = split_message(writing_tool_result_text(result))
        for index, chunk in enumerate(chunks):
            if index:
                await asyncio.sleep(1)
            send = progress.edit_text if index == 0 else update.message.reply_text
            while True:
                try:
                    await send(chunk)
                    break
                except RetryAfter as exc:
                    delay = exc.retry_after
                    seconds = delay.total_seconds() if hasattr(delay, "total_seconds") else float(delay)
                    await asyncio.sleep(seconds + 1)
    except Exception as exc:
        logger.exception("Failed to execute writing-tech-doc tool: %s", tool)
        await progress.edit_text(f"{tool} 실행 중 오류가 발생했습니다.\n{exc}")


async def boost_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        arguments = parse_boost_command(command_argument_text(update))
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    await execute_writing_tool(update, context, "boost", arguments)


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    mode = command_argument_text(update).strip().lower() or "recent"
    if mode not in {"recent", "all", "full"}:
        await update.message.reply_text("사용법: /list (최근 10개), /list all (최대 50개), /list full (전체)")
        return
    await execute_writing_tool(update, context, "list", {"mode": mode})


def allom_message_content(update: Update) -> str:
    note = command_argument_text(update)
    original = getattr(update.effective_message, "reply_to_message", None)
    if original is None:
        if not note.strip():
            raise ValueError("저장할 메모를 입력하거나 저장할 메시지에 답장으로 /allom을 보내세요.")
        return note

    content = getattr(original, "text", None) or getattr(original, "caption", None)
    if not content or not content.strip():
        raise ValueError("답장한 메시지에 저장할 텍스트나 설명이 없습니다. 사진·파일 자체는 저장하지 않습니다.")
    sender = getattr(original, "sender_chat", None) or getattr(original, "from_user", None)
    source = {
        "chat_id": getattr(getattr(original, "chat", None), "id", None),
        "message_id": getattr(original, "message_id", None),
        "author_id": getattr(sender, "id", None),
        "author_name": (getattr(sender, "title", None) or getattr(sender, "full_name", None)
                        or getattr(sender, "username", None)),
        "username": getattr(sender, "username", None),
    }
    result = "## 원본 메시지\n\n" + content
    if note.strip():
        result += "\n\n## 추가 메모\n\n" + note
    # Stable provenance keeps repeated saves of the same reply deduplicatable.
    result += "\n\n## Telegram 원본 출처\n\n```json\n" + json.dumps(source, ensure_ascii=False, indent=2) + "\n```\n"
    return result


async def allom_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        content = allom_message_content(update)
        arguments = {"content": content, **telegram_allom_identity(update)}
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    await execute_writing_tool(update, context, "allom", arguments)


async def recall_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = command_argument_text(update).strip()
    if len(query) >= 2 and query[0] in ('"', "'") and query[-1] == query[0]:
        query = query[1:-1].strip()
    if not query:
        await update.message.reply_text('검색어를 입력해 주세요. 예: /recall "피지컬AI"')
        return
    await execute_writing_tool(update, context, "recall", {"query": query})


async def findm_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        arguments = parse_findm_command(command_argument_text(update))
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    await execute_writing_tool(update, context, "findm", arguments)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    await update.message.reply_text(
        "프롬프트를 보내면 Gemma4 Ollama 서버에 전달합니다. "
        "문서 도구는 /boost, /list, /ls, /allom, /findm, /recall 명령으로 사용할 수 있습니다."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    await update.message.reply_text(
        "사용법:\n"
        "1. 이 채팅창에 질문이나 프롬프트를 입력합니다.\n"
        "2. 봇이 Gemma4 서버의 /api/enqueue-generate로 전송합니다.\n"
        "3. 생성된 답변을 다시 전달합니다.\n\n"
        "문서 도구:\n"
        "/boost [--dry-run] [파일명] - Markdown 기술 문서 보강\n"
        "/list 또는 /ls - 최근 10개 파일과 WebDAV 경로\n"
        "/list all - 최대 50개, 초과 시 /list full 안내\n"
        "/list full - 모든 항목을 나누어 회신\n"
        "/allom 메모 내용 - 방·토픽·작성자별 WebDAV 메모 저장\n"
        "/allom (메시지에 답장) - 원본 텍스트·설명 저장, 뒤에 추가 메모 입력 가능\n"
        '/recall "단어" - 내용이 일치하는 Markdown 파일 목록과 전체 내용\n'
        "/findm [--page-size N] [--author ID] [--room ID] [--topic ID] 검색어 - 메모와 원본 문서 검색"
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
    temp_image_paths: list[Path] = []
    raw_answer = ""
    try:
        images, temp_image_paths = await image_payloads_from_update(update, context) if has_photo else ([], [])
        if has_photo:
            logger.info("Sending prompt to LLM with image_count=%s", len(images))
        enqueue_response = enqueue_llm_prompt(prompt, images, {
            "source": "telegram",
            "room_id": f"{update.effective_chat.id}:{update.message.message_thread_id or 0}",
            "sender_id": str(update.effective_user.id) if update.effective_user else "unknown",
        })
        thinking_message = await update.message.reply_text(f"thinking...\n{queue_line_from_response(enqueue_response)}")
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        job_id = int(enqueue_response.get("prompt_queue_id"))
        result = await wait_for_prompt_result(job_id)
        raw_answer = str(result.get("visible_response") or result.get("answer") or result.get("response") or "").strip()
        answer = append_telegram_response_summary(format_llm_response(result), update, context)
    except Exception as exc:
        cleanup_temp_image_paths(temp_image_paths)
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

    detection_paths = await asyncio.to_thread(render_detection_box_images, temp_image_paths, raw_answer or answer)
    plot_paths = detection_paths
    if not detection_paths:
        plot_paths = await asyncio.to_thread(render_model_plot_images, answer)
    try:
        for index, plot_path in enumerate(plot_paths, start=1):
            caption = f"YOLO detection boxes {index}" if plot_path.parent.name.startswith("telegram_yolo_detection_") else f"Generated plot {index}"
            with plot_path.open("rb") as photo:
                await update.message.reply_photo(photo=photo, caption=caption)
    finally:
        cleanup_generated_plot_images(plot_paths)
        cleanup_temp_image_paths(temp_image_paths)


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN 환경 변수를 설정하세요.")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("boost", boost_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("ls", list_command))
    application.add_handler(CommandHandler("allom", allom_command))
    application.add_handler(CommandHandler("findm", findm_command))
    application.add_handler(CommandHandler("recall", recall_command))
    application.add_handler(MessageHandler((filters.TEXT | filters.PHOTO | filters.Document.IMAGE) & ~filters.COMMAND, handle_prompt))

    keep_recent_pending_updates(MAX_PENDING_UPDATES_ON_STARTUP)
    logger.info(
        "Telegram bot started. LLM_API_URL=%s writing_tool_url=%s prefixes=%s allowed_user_ids_file=%s allowed_user_count=%s",
        LLM_API_URL,
        WRITING_TECH_DOC_TOOL_URL,
        mention_prefixes(TELEGRAM_BOT_USERNAMES),
        ALLOWED_TELEGRAM_USER_IDS_FILE,
        len(allowed_telegram_user_ids()),
    )
    application.run_polling()


if __name__ == "__main__":
    main()
