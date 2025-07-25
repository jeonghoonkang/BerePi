import os
import time
import threading

import streamlit as st
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline


def rerun() -> None:
    """Compatibility helper to rerun the Streamlit script."""
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    else:
        st.rerun()


def display_gpu_status() -> None:
    """Display current GPU status at startup."""
    try:
        import torch

        if torch.cuda.is_available():
            gpus = [f"{i}: {torch.cuda.get_device_name(i)}" for i in range(torch.cuda.device_count())]
            st.info("GPU available: " + ", ".join(gpus))
        else:
            st.info("GPU not available, using CPU")
    except Exception as exc:
        st.warning(f"Could not determine GPU status: {exc}")

st.set_page_config(page_title="Qwen Q&A", page_icon="🎃")

st.title("Qwen 기반 Q&A 데모")
display_gpu_status()


def download_model(model_name: str) -> None:
    """Download the model showing a simple progress bar."""
    try:
        from huggingface_hub import snapshot_download
    except Exception:
        st.error("huggingface_hub is required to download models")
        st.stop()

    progress = st.progress(0)

    def _download():
        try:
            snapshot_download(repo_id=model_name, local_dir=model_name, resume_download=True)
        except Exception as exc:
            st.session_state.download_error = str(exc)

    thread = threading.Thread(target=_download)
    thread.start()
    pct = 0
    while thread.is_alive():
        pct = min(100, pct + 1)
        progress.progress(pct / 100.0)
        time.sleep(1)

    thread.join()
    progress.progress(1.0)
    if "download_error" in st.session_state:
        st.error("Failed to download model: " + st.session_state.download_error)
        st.stop()
    st.success("Download complete")


def ensure_model(model_name: str) -> None:
    """Ensure the model files are available. Auto download after 10s."""
    if os.path.isdir(model_name):
        return
    try:
        from huggingface_hub import hf_hub_download

        hf_hub_download(repo_id=model_name, filename="config.json", local_files_only=True)
        return
    except Exception:
        pass

    if "prompt_time" not in st.session_state:
        st.session_state.prompt_time = time.time()

    elapsed = time.time() - st.session_state.prompt_time
    remaining = int(10 - elapsed)

    if "download_decision" not in st.session_state:
        st.session_state.download_decision = None

    if st.session_state.download_decision is None:
        st.warning(f"Model '{model_name}' not found. Download? (auto in {max(remaining,0)}s)")
        cols = st.columns(2)
        if cols[0].button("Download now"):
            st.session_state.download_decision = True
            rerun()

        if cols[1].button("Cancel"):
            st.session_state.download_decision = False
            st.stop()
        if remaining <= 0:
            st.session_state.download_decision = True
            rerun()
        else:
            time.sleep(1)
            rerun()

    elif st.session_state.download_decision:
        download_model(model_name)
    else:
        st.stop()

MODEL_NAME = os.environ.get("QWEN_MODEL", "Qwen/Qwen1.5-7B-Chat")
ensure_model(MODEL_NAME)


@st.cache_resource
def load_model(name: str):
    tokenizer = AutoTokenizer.from_pretrained(name)
    model = AutoModelForCausalLM.from_pretrained(name)
    generator = pipeline("text-generation", model=model, tokenizer=tokenizer)
    return generator


generator = load_model(MODEL_NAME)

prompt = st.text_input("질문을 입력하세요:")
error_area = st.empty()
if prompt:
    try:
        with st.spinner("답변 생성 중..."):
            response = generator(prompt, max_length=512, do_sample=True)
        st.write(response[0]["generated_text"][len(prompt):].strip())
    except Exception as exc:  # pragma: no cover - GUI display
        error_area.error("답변 생성 중 오류가 발생했습니다.")
        with st.expander("오류 상세 보기"):
            st.exception(exc)
