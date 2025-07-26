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


def display_gpu_status(tokenizer=None) -> None:
    """Display current GPU and model info at startup."""
    try:
        import torch

        # 애플 실리콘 MPS 지원 확인
        if torch.backends.mps.is_available():
            st.info("Apple Silicon GPU (MPS) available")
            try:
                # MPS 디바이스 정보 표시
                device = torch.device("mps")
                st.info(f"Using device: {device}")
            except Exception as e:
                st.warning(f"MPS device error: {e}")
        elif torch.cuda.is_available():
            gpu_names = [f"{i}: {torch.cuda.get_device_name(i)}" for i in range(torch.cuda.device_count())]
            st.info("GPU available: " + ", ".join(gpu_names))

            mem_info = []
            for i in range(torch.cuda.device_count()):
                total = torch.cuda.get_device_properties(i).total_memory // (1024 ** 2)
                allocated = torch.cuda.memory_allocated(i) // (1024 ** 2)
                mem_info.append(f"{i}: {allocated}MB/{total}MB")
            st.info("GPU memory usage: " + ", ".join(mem_info))
        else:
            st.info("GPU not available, using CPU")
    except Exception as exc:  # pragma: no cover - GPU inspection can fail
        st.warning(f"Could not determine GPU status: {exc}")

    if tokenizer is not None:
        try:
            st.info(f"Max input tokens: {getattr(tokenizer, 'model_max_length', 'unknown')}")
        except Exception:  # pragma: no cover - tokenizer may be malformed
            pass

st.set_page_config(page_title="Qwen Q&A", page_icon="🎃")

st.title("Qwen 기반 Q&A 데모")



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
    import torch
    
    tokenizer = AutoTokenizer.from_pretrained(name)
    
    # 애플 실리콘 MPS 디바이스 우선 사용
    if torch.backends.mps.is_available():
        device = torch.device("mps")
        model = AutoModelForCausalLM.from_pretrained(name, device_map=device)
        generator = pipeline("text-generation", model=model, tokenizer=tokenizer, device=device)
    else:
        # 기존 CUDA 또는 CPU 사용
        model = AutoModelForCausalLM.from_pretrained(name, device_map="auto")
        generator = pipeline("text-generation", model=model, tokenizer=tokenizer)

    return generator


generator = load_model(MODEL_NAME)
display_gpu_status(generator.tokenizer)

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
