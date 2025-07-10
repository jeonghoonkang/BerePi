import os
import time
import threading


import streamlit as st
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

st.set_page_config(page_title="Korean Tourism Q&A", page_icon="\ud83c\udf0d")

st.title("\ud83c\uddf0\ud83c\uddf7 Korean Tourism Q&A with Llama 3")


def download_model(model_name: str) -> None:
    """Download the model showing a simple progress bar."""
    try:
        from huggingface_hub import snapshot_download
    except Exception:
        st.error("huggingface_hub is required to download models")
        st.stop()

    progress = st.progress(0)

    def _download():
        snapshot_download(repo_id=model_name, local_dir=model_name, resume_download=True)

    thread = threading.Thread(target=_download)
    thread.start()
    pct = 0
    while thread.is_alive():
        pct = min(100, pct + 1)
        progress.progress(pct / 100.0)
        time.sleep(1)
    progress.progress(1.0)
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
            st.experimental_rerun()
        if cols[1].button("Cancel"):
            st.session_state.download_decision = False
            st.stop()
        if remaining <= 0:
            st.session_state.download_decision = True
            st.experimental_rerun()
        else:
            time.sleep(1)
            st.experimental_rerun()
    elif st.session_state.download_decision:
        download_model(model_name)
    else:
        st.stop()

MODEL_NAME = os.environ.get("LLAMA3_MODEL", "meta-llama/Meta-Llama-3-8B-Instruct")
ensure_model(MODEL_NAME)

# Load model only once
@st.cache_resource
def load_model(name: str):
    tokenizer = AutoTokenizer.from_pretrained(name)
    model = AutoModelForCausalLM.from_pretrained(name)
    generator = pipeline("text-generation", model=model, tokenizer=tokenizer)
    return generator

generator = load_model(MODEL_NAME)

prompt = st.text_input("Ask about tourism in Korea:")
if prompt:
    with st.spinner("Generating answer..."):
        # We limit max length to keep response quick
        response = generator(prompt, max_length=512, do_sample=True)
        st.write(response[0]["generated_text"][len(prompt):].strip())
