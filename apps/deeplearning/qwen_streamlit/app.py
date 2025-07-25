import os
import threading
import time

import streamlit as st
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch


def download_model(model_name: str) -> None:
    """Download the model showing a progress bar."""
    try:
        from huggingface_hub import snapshot_download
    except Exception:
        st.error("huggingface_hub is required to download models")
        st.stop()

    progress = st.progress(0)

    def _download() -> None:
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
    """Ensure model files are available, otherwise download them."""
    if os.path.isdir(model_name):
        return
    try:
        from huggingface_hub import hf_hub_download

        hf_hub_download(repo_id=model_name, filename="config.json", local_files_only=True)
        return
    except Exception:
        pass

    download_model(model_name)



def load_model(model_name: str):
    """Load the tokenizer and model."""
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    return tokenizer, model, device


def generate_response(prompt: str, tokenizer, model, device):
    """Generate text from the model given a prompt."""
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model.generate(**inputs, max_new_tokens=128)
    return tokenizer.decode(outputs[0], skip_special_tokens=True)


st.title("Qwen Chat")
model_name = "Qwen/Qwen1.5-0.5B-Chat"

ensure_model(model_name)

@st.cache_resource
def get_model():
    return load_model(model_name)


prompt = st.text_input("Enter a sentence")
if prompt:
    tokenizer, model, device = get_model()
    response = generate_response(prompt, tokenizer, model, device)
    st.write(response)
