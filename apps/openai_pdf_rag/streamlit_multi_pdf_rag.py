
import os
import subprocess
from typing import List

import numpy as np
import streamlit as st
from openai import BadRequestError, OpenAI
from PyPDF2 import PdfReader


MODEL_OPTIONS = {
    "gpt-3.5-turbo": "gpt-3.5-turbo",
    "gpt-4o-mini": "gpt-4o-mini",
    "llama-3": "meta-llama/Meta-Llama-3-8B-Instruct",
    "mistral": "mistralai/Mistral-7B-Instruct-v0.2",
    "gemma": "google/gemma-2b-it",
}


def _verify_model_files(path: str) -> bool:
    config = os.path.join(path, "config.json")
    if not os.path.isfile(config) or os.path.getsize(config) <= 0:
        return False
    weights = [f for f in os.listdir(path) if f.endswith((".bin", ".safetensors"))]
    if not weights:
        return False
    for wf in weights:
        if os.path.getsize(os.path.join(path, wf)) <= 0:
            return False
    return True


def ensure_model(repo_id: str) -> None:
    if os.path.isdir(repo_id) and _verify_model_files(repo_id):
        return
    try:
        from huggingface_hub import hf_hub_download, snapshot_download
    except Exception:
        st.error("huggingface_hub 라이브러리가 필요합니다.")
        st.stop()

    def _download() -> None:
        with st.spinner("모델 다운로드 중..."):
            snapshot_download(repo_id=repo_id, local_dir=repo_id, resume_download=True)
        if _verify_model_files(repo_id):
            st.success("다운로드 완료")
        else:
            st.error("모델 파일 검증 실패")
            st.stop()

    try:
        hf_hub_download(repo_id=repo_id, filename="config.json", local_files_only=True)
        if not _verify_model_files(repo_id):
            _download()
    except Exception:
        if st.button(f"{repo_id} 다운로드"):
            _download()
        else:
            st.stop()


def get_gpu_info() -> str:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            stderr=subprocess.DEVNULL,
        )
        gpus = [g for g in out.decode().strip().split("\n") if g]
        return f"{len(gpus)}개 ({', '.join(gpus)})" if gpus else "GPU 없음"
    except Exception:
        return "GPU 없음"

def load_api_key() -> str | None:
    """Read the OpenAI API key from a nocommit.txt file."""
    paths = [
        os.path.join(os.path.dirname(__file__), "nocommit.txt"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "nocommit.txt"),
    ]
    for path in paths:
        if os.path.exists(path):
            with open(path) as f:
                return f.read().strip()
    return None


api_key = load_api_key()
if not api_key:
    st.error("nocommit.txt 파일에서 OpenAI API 키를 찾을 수 없습니다.")
    st.stop()

client = OpenAI(api_key=api_key)

st.set_page_config(page_title="PDF RAG Chat")
st.title("📄 PDF RAG Chat")
st.write(f"사용 가능한 GPU: {get_gpu_info()}")

model_name = st.selectbox("모델 선택", list(MODEL_OPTIONS.keys()))
model = MODEL_OPTIONS[model_name]
if model_name in ["llama-3", "mistral", "gemma"]:
    ensure_model(model)
st.caption(f"사용 모델: {model_name}")

if "errors" not in st.session_state:
    st.session_state.errors = []


def log_error(msg: str) -> None:
    st.session_state.errors.append(msg)
    st.session_state.errors = st.session_state.errors[-3:]


def reset_app() -> None:
    for key in list(st.session_state.keys()):
        if key != "errors":
            del st.session_state[key]
    st.rerun()


uploaded_files = st.file_uploader(
    "PDF 파일을 업로드하세요", type="pdf", accept_multiple_files=True
)


if uploaded_files:
    st.subheader("업로드된 파일")
    for f in uploaded_files:
        st.write(f"- {f.name}")


def read_pdf(file) -> str:
    text = ""
    reader = PdfReader(file)
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text


def split_text(text: str, chunk_size: int = 800, overlap: int = 200) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


all_chunks: List[str] = []
embeddings: List[np.ndarray] = []
if uploaded_files:
    for uf in uploaded_files:
        pdf_text = read_pdf(uf)
        all_chunks.extend(split_text(pdf_text))

    with st.spinner("임베딩 생성 중..."):
        for chunk in all_chunks:
            emb_resp = client.embeddings.create(
                model="text-embedding-3-small", input=chunk
            )
            emb = emb_resp.data[0].embedding

            embeddings.append(np.array(emb))
    st.success("임베딩 생성 완료")

st.markdown("---")
question = st.text_input("질문을 입력하세요")

if question:
    if embeddings:
        q_emb_resp = client.embeddings.create(
            model="text-embedding-3-small", input=question
        )
        q_emb = np.array(q_emb_resp.data[0].embedding)


        sims = [
            float(np.dot(q_emb, e) / (np.linalg.norm(q_emb) * np.linalg.norm(e)))
            for e in embeddings
        ]
        top_indices = np.argsort(sims)[-3:][::-1]
        context = "\n\n".join(all_chunks[i] for i in top_indices)

        prompt = (
            "다음 문서 내용을 참고하여 질문에 답변하세요.\n\n"
            + context
            + "\n\n질문: "
            + question
        )
        with st.spinner("RAG 답변 생성 중..."):
            try:
                completion = client.responses.create(model=model, input=prompt)
            except BadRequestError as e:
                log_error(str(e))
                reset_app()
        rag_answer = completion.output_text

        st.text_area("RAG 답변", rag_answer, height=200)
    else:
        st.warning("먼저 PDF 파일을 업로드하세요.")

    with st.spinner("일반 답변 생성 중..."):
        try:
            direct_completion = client.responses.create(model=model, input=question)
        except BadRequestError as e:
            log_error(str(e))
            reset_app()
    direct_answer = direct_completion.output_text

    st.text_area("일반 모델 답변", direct_answer, height=200)

if st.session_state.errors:
    st.markdown("---")
    st.subheader("에러 메시지")
    for err in st.session_state.errors[-3:]:
        st.error(err)

