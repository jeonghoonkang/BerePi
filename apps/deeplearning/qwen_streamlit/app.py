import os
import sys
import threading
import time

from rich.progress import (
    BarColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
)
import streamlit as st
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch


def download_model_cli(model_name: str) -> None:
    """Download the model showing a Rich progress bar."""
    try:
        from huggingface_hub import snapshot_download
    except Exception:
        print("huggingface_hub is required to download models", file=sys.stderr)
        sys.exit(1)

    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
    )
    task = progress.add_task("Downloading model...", total=100)

    def _download() -> None:
        try:
            snapshot_download(repo_id=model_name, local_dir=model_name, resume_download=True)
        except Exception as exc:
            progress.stop()
            print(f"Failed to download model: {exc}", file=sys.stderr)
            sys.exit(1)

    thread = threading.Thread(target=_download)
    thread.start()
    pct = 0
    with progress:
        while thread.is_alive():
            pct = min(100, pct + 1)
            progress.update(task, completed=pct)
            time.sleep(1)
        thread.join()
        progress.update(task, completed=100)


def ensure_model_cli(model_name: str) -> None:
    """Ensure model files are available, otherwise download them."""
    if os.path.isdir(model_name):
        return
    try:
        from huggingface_hub import hf_hub_download

        hf_hub_download(repo_id=model_name, filename="config.json", local_files_only=True)
        return
    except Exception:
        pass

    download_model_cli(model_name)



def load_model(model_name: str):
    """Load the tokenizer and model."""
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name)
    if torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"
    model.to(device)
    return tokenizer, model, device


def generate_response(prompt: str, tokenizer, model, device):
    """Generate text from the model given a prompt."""
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model.generate(**inputs, max_new_tokens=128)
    return tokenizer.decode(outputs[0], skip_special_tokens=True)


MODEL_CHOICES = {
    "Qwen1.5-0.5B-Chat": "Qwen/Qwen1.5-0.5B-Chat",
    "Qwen1.5-1.8B-Chat (GGUF)": "Qwen/Qwen1.5-1.8B-Chat-GGUF",
}

st.title("Qwen Chat")

choice = st.sidebar.selectbox("Model", list(MODEL_CHOICES.keys()))
MODEL_NAME = MODEL_CHOICES[choice]

ensure_model_cli(MODEL_NAME)


@st.cache_resource
def get_model(name: str):
    return load_model(name)


prompt = st.text_input("\U0001F464 질문을 입력하세요:")
if prompt:
    tokenizer, model, device = get_model(MODEL_NAME)
    response = generate_response(prompt, tokenizer, model, device)
    st.write(f"\U0001F916 {response}")
