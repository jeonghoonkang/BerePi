from __future__ import annotations

import base64
import io
import json
import os
import shutil
import subprocess
from typing import Iterable

import pandas as pd
import requests
import streamlit as st
from PIL import Image

DEFAULT_OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")
REQUEST_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "600"))
MAX_PREVIEW_ROWS = 20
GEMMA_MODEL_OPTIONS = [
    "gemma3:1b",
    "gemma3:4b",
    "gemma3:12b",
    "gemma3:27b",
]

MODEL_MEMORY_GUIDE_GB = {
    "gemma3:1b": 4,
    "gemma3:4b": 8,
    "gemma3:12b": 20,
    "gemma3:27b": 40,
}


def excel_to_context(uploaded_file) -> str:
    """Create a concise, prompt-friendly summary from an Excel workbook."""
    uploaded_file.seek(0)
    workbook = pd.ExcelFile(uploaded_file)
    sections: list[str] = []

    for sheet_name in workbook.sheet_names:
        frame = workbook.parse(sheet_name)
        preview = frame.head(MAX_PREVIEW_ROWS).fillna("")
        preview_csv = preview.to_csv(index=False)
        sections.append(
            "\n".join(
                [
                    f"[Sheet] {sheet_name}",
                    f"Rows: {len(frame)}",
                    f"Columns: {len(frame.columns)}",
                    "Column names: " + ", ".join(str(column) for column in frame.columns),
                    f"Preview ({min(len(preview), MAX_PREVIEW_ROWS)} rows):",
                    preview_csv.strip(),
                ]
            )
        )

    return "\n\n".join(sections)


def image_to_base64(uploaded_file) -> tuple[str, Image.Image]:
    """Return a base64 string for Ollama and a PIL preview image."""
    data = uploaded_file.getvalue()
    encoded = base64.b64encode(data).decode("utf-8")
    image = Image.open(io.BytesIO(data))
    return encoded, image


def build_user_message(prompt: str, excel_contexts: Iterable[str]) -> str:
    """Build the final prompt content sent to the model."""
    content_parts = [prompt.strip()]

    excel_contexts = [context for context in excel_contexts if context.strip()]
    if excel_contexts:
        content_parts.append(
            "The user also uploaded Excel data. Use the workbook summaries below when relevant.\n\n"
            + "\n\n".join(excel_contexts)
        )

    return "\n\n".join(part for part in content_parts if part)


def call_ollama(host: str, model: str, prompt: str, excel_contexts: list[str], images: list[str]) -> str:
    """Send a chat request to Ollama."""
    url = f"{host.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant running on an RTX 5090 server. "
                    "Answer clearly, use uploaded Excel context when provided, and analyze images when attached."
                ),
            },
            {
                "role": "user",
                "content": build_user_message(prompt, excel_contexts),
                "images": images,
            },
        ],
    }

    response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    data = response.json()
    return data.get("message", {}).get("content", "").strip()


def fetch_installed_models(host: str) -> list[str]:
    """Return installed Ollama model names."""
    response = requests.get(f"{host.rstrip('/')}/api/tags", timeout=30)
    response.raise_for_status()
    data = response.json()
    models = data.get("models", [])
    return sorted(
        {
            model.get("name", "").strip()
            for model in models
            if model.get("name", "").strip()
        }
    )


def detect_gpu_info() -> tuple[str | None, int | None, str | None]:
    """Detect GPU name and memory in GiB using nvidia-smi when available."""
    if not shutil.which("nvidia-smi"):
        return None, None, "nvidia-smi not found"

    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        return None, None, str(exc)

    first_line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    if not first_line:
        return None, None, "No GPU information returned"

    parts = [part.strip() for part in first_line.split(",", maxsplit=1)]
    if len(parts) != 2:
        return None, None, f"Unexpected nvidia-smi output: {first_line}"

    gpu_name = parts[0]
    try:
        memory_mib = int(parts[1])
    except ValueError:
        return gpu_name, None, f"Unexpected memory value: {parts[1]}"

    memory_gib = max(memory_mib // 1024, 1)
    return gpu_name, memory_gib, None


def recommend_models_for_gpu(memory_gib: int | None) -> tuple[str | None, list[str]]:
    """Return a recommended default model and compatible model list."""
    if memory_gib is None:
        return None, []

    compatible_models = [
        model_name
        for model_name, required_gb in MODEL_MEMORY_GUIDE_GB.items()
        if memory_gib >= required_gb
    ]

    if not compatible_models:
        return "gemma3:1b", ["gemma3:1b"]

    return compatible_models[-1], compatible_models


def pull_model(host: str, model: str, status_placeholder, progress_placeholder) -> None:
    """Download a model from Ollama and show progress in the sidebar."""
    response = requests.post(
        f"{host.rstrip('/')}/api/pull",
        json={"model": model, "stream": True},
        timeout=REQUEST_TIMEOUT,
        stream=True,
    )
    response.raise_for_status()

    progress_bar = progress_placeholder.progress(0)
    last_status = "Starting download..."
    status_placeholder.info(last_status)

    for raw_line in response.iter_lines():
        if not raw_line:
            continue

        event = json.loads(raw_line.decode("utf-8"))
        status_text = event.get("status", last_status)
        total = event.get("total")
        completed = event.get("completed")

        if total and completed is not None and total > 0:
            ratio = min(max(completed / total, 0.0), 1.0)
            progress_bar.progress(ratio, text=status_text)
        else:
            progress_bar.progress(0, text=status_text)

        last_status = status_text
        status_placeholder.info(status_text)

    progress_bar.progress(1.0, text="Download complete")
    status_placeholder.success(f"Model download completed: {model}")


def render_sidebar() -> tuple[str, str]:
    st.sidebar.header("Runtime")
    host = st.sidebar.text_input("Ollama Host", value=DEFAULT_OLLAMA_HOST)
    refresh_models = st.sidebar.button("Refresh Installed Models", use_container_width=True)

    if refresh_models or "installed_models" not in st.session_state:
        try:
            st.session_state.installed_models = fetch_installed_models(host)
            st.session_state.model_error = ""
        except requests.RequestException as exc:
            st.session_state.installed_models = []
            st.session_state.model_error = f"Failed to load installed models: {exc}"

    installed_models = st.session_state.get("installed_models", [])
    model_candidates = list(dict.fromkeys(GEMMA_MODEL_OPTIONS + installed_models))
    gpu_name, gpu_memory_gib, gpu_error = detect_gpu_info()
    recommended_model, compatible_models = recommend_models_for_gpu(gpu_memory_gib)

    if "preferred_model" not in st.session_state:
        st.session_state.preferred_model = recommended_model or DEFAULT_MODEL

    if "auto_select_downloaded_model" not in st.session_state:
        st.session_state.auto_select_downloaded_model = True

    if st.session_state.get("selected_model") not in model_candidates:
        preferred = st.session_state.get("preferred_model", DEFAULT_MODEL)
        if preferred in model_candidates:
            st.session_state.selected_model = preferred
        elif DEFAULT_MODEL in model_candidates:
            st.session_state.selected_model = DEFAULT_MODEL
        else:
            st.session_state.selected_model = model_candidates[0]

    st.sidebar.subheader("GPU Recommendation")
    if gpu_name and gpu_memory_gib:
        st.sidebar.write(f"GPU: `{gpu_name}`")
        st.sidebar.write(f"Memory: `{gpu_memory_gib} GiB`")
        if recommended_model:
            st.sidebar.success(f"Recommended default: `{recommended_model}`")
        if compatible_models:
            st.sidebar.caption("Fits this GPU")
            for compatible_model in compatible_models:
                st.sidebar.code(compatible_model)
    else:
        st.sidebar.info("GPU memory could not be detected automatically.")
        if gpu_error:
            st.sidebar.caption(gpu_error)

    selected_model = st.sidebar.selectbox(
        "Model Select",
        options=model_candidates,
        index=model_candidates.index(st.session_state.selected_model),
    )
    st.session_state.selected_model = selected_model

    custom_model = st.sidebar.text_input("Custom Model Tag", value=selected_model)
    model = custom_model.strip() or selected_model

    if st.session_state.get("model_error"):
        st.sidebar.warning(st.session_state.model_error)

    with st.sidebar.expander("Installed Models", expanded=False):
        if installed_models:
            for installed_model in installed_models:
                st.write(f"- {installed_model}")
        else:
            st.write("No installed models found.")

    st.session_state.auto_select_downloaded_model = st.sidebar.checkbox(
        "Auto-select downloaded model",
        value=st.session_state.auto_select_downloaded_model,
    )

    if recommended_model and st.sidebar.button("Use Recommended Model", use_container_width=True):
        st.session_state.preferred_model = recommended_model
        st.session_state.selected_model = recommended_model
        st.rerun()

    st.sidebar.markdown("Recommended model options")
    for option in GEMMA_MODEL_OPTIONS:
        required_gb = MODEL_MEMORY_GUIDE_GB.get(option)
        label = f"{option}  ({required_gb} GiB+ recommended)" if required_gb else option
        st.sidebar.code(label)

    status_placeholder = st.sidebar.empty()
    progress_placeholder = st.sidebar.empty()
    if st.sidebar.button("Download Selected Model", type="primary", use_container_width=True):
        try:
            pull_model(host, model, status_placeholder, progress_placeholder)
            st.session_state.installed_models = fetch_installed_models(host)
            st.session_state.preferred_model = model
            if st.session_state.auto_select_downloaded_model:
                st.session_state.selected_model = model
            st.rerun()
        except requests.RequestException as exc:
            status_placeholder.error(f"Model download failed: {exc}")

    st.sidebar.markdown("Example: `OLLAMA_HOST=http://127.0.0.1:11434 ollama serve`")

    return host, model


def main() -> None:
    st.set_page_config(page_title="Gemma 3 4B on RTX 5090", layout="wide")
    st.title("Gemma 3 4B Chat for RTX 5090")
    st.caption("Ollama + Streamlit with text, Excel, and image inputs")

    host, model = render_sidebar()

    if "history" not in st.session_state:
        st.session_state.history = []

    prompt = st.text_area(
        "Prompt",
        height=180,
        placeholder="질문을 입력하세요. 엑셀 파일이나 이미지를 함께 올리면 같이 분석합니다.",
    )

    uploaded_excels = st.file_uploader(
        "Excel files",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
    )
    uploaded_images = st.file_uploader(
        "Image files",
        type=["png", "jpg", "jpeg", "webp", "bmp"],
        accept_multiple_files=True,
    )

    excel_contexts: list[str] = []
    if uploaded_excels:
        st.subheader("Excel Preview")
        for uploaded_excel in uploaded_excels:
            try:
                context = excel_to_context(uploaded_excel)
                excel_contexts.append(context)
                uploaded_excel.seek(0)
                workbook = pd.ExcelFile(uploaded_excel)
                st.write(f"Workbook: `{uploaded_excel.name}`")
                for sheet_name in workbook.sheet_names:
                    frame = workbook.parse(sheet_name)
                    st.write(f"Sheet: `{sheet_name}`")
                    st.dataframe(frame.head(MAX_PREVIEW_ROWS), use_container_width=True)
            except Exception as exc:
                st.error(f"Failed to read Excel file {uploaded_excel.name}: {exc}")

    image_payloads: list[str] = []
    if uploaded_images:
        st.subheader("Image Preview")
        columns = st.columns(min(len(uploaded_images), 3))
        for index, uploaded_image in enumerate(uploaded_images):
            try:
                image_base64, image = image_to_base64(uploaded_image)
                image_payloads.append(image_base64)
                with columns[index % len(columns)]:
                    st.image(image, caption=uploaded_image.name, use_container_width=True)
            except Exception as exc:
                st.error(f"Failed to read image {uploaded_image.name}: {exc}")

    ask_disabled = not prompt.strip()
    if st.button("Ask Gemma", type="primary", disabled=ask_disabled):
        with st.spinner("Gemma is generating a response..."):
            try:
                answer = call_ollama(host, model, prompt, excel_contexts, image_payloads)
                st.session_state.history.append(
                    {
                        "prompt": prompt,
                        "answer": answer,
                    }
                )
                st.success("Response received")
            except requests.HTTPError as exc:
                detail = exc.response.text if exc.response is not None else str(exc)
                st.error(f"Ollama request failed: {detail}")
            except requests.RequestException as exc:
                st.error(f"Failed to connect to Ollama at {host}: {exc}")
            except Exception as exc:
                st.error(f"Unexpected error: {exc}")

    if st.session_state.history:
        st.subheader("Chat History")
        for item in reversed(st.session_state.history):
            st.markdown("**Prompt**")
            st.write(item["prompt"])
            st.markdown("**Answer**")
            st.write(item["answer"])


if __name__ == "__main__":
    main()
