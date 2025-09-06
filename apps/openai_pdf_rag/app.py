import os
import io
import subprocess
import time
import numpy as np
import pandas as pd
from fpdf import FPDF

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


def load_hf_token() -> str | None:
    token = os.getenv("HF_TOKEN")
    if token:
        return token.strip()
    token_paths = [
        os.path.join(os.path.dirname(__file__), "hf_token.txt"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "hf_token.txt"),
    ]
    for path in token_paths:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
    return None


def _verify_model_files(path: str) -> bool:
    config = os.path.join(path, "config.json")
    if not os.path.isfile(config) or os.path.getsize(config) <= 0:
        return False
    weight_files = [
        f
        for f in os.listdir(path)
        if f.endswith((".bin", ".safetensors"))
    ]
    if not weight_files:
        return False
    for wf in weight_files:
        if os.path.getsize(os.path.join(path, wf)) <= 0:
            return False
    return True


def ensure_model(repo_id: str) -> None:
    """Ensure that an OSS model is downloaded and valid before use."""
    if os.path.isdir(repo_id) and _verify_model_files(repo_id):
        return
    try:
        from huggingface_hub import hf_hub_download, snapshot_download, login
        from huggingface_hub.utils import GatedRepoError

    except Exception:
        st.error("huggingface_hub 라이브러리가 필요합니다.")
        st.stop()

    token = load_hf_token()
    if token:
        try:
            login(token=token)
        except Exception:
            st.error("Hugging Face 로그인 실패")
            st.stop()

    def _download() -> None:
        with st.spinner("모델 다운로드 중..."):
            try:
                snapshot_download(
                    repo_id=repo_id,
                    local_dir=repo_id,
                    force_download=True,

                    token=token,
                )
            except GatedRepoError:
                st.error(
                    "허깅페이스 토큰이 필요합니다. HF_TOKEN 환경변수 또는 hf_token.txt 파일을 설정하세요."
                )
                st.stop()
            except ValueError as e:
                st.error(f"모델 다운로드 실패: {e}")
                st.stop()
            except Exception as e:
                st.error(f"모델 다운로드 중 오류 발생: {e}")
                st.stop()

        if _verify_model_files(repo_id):
            st.success("다운로드 완료")
        else:
            st.error("모델 파일 검증 실패")
            st.stop()

    try:
        hf_hub_download(
            repo_id=repo_id,
            filename="config.json",
            local_files_only=True,
            token=token,
        )
        if not _verify_model_files(repo_id):
            _download()
    except GatedRepoError:
        st.error(
            "허깅페이스 토큰이 필요합니다. HF_TOKEN 환경변수 또는 hf_token.txt 파일을 설정하세요."
        )
        st.stop()
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
      
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    key_candidates = [
        os.path.join(os.path.dirname(__file__), "nocommit_key.txt"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "nocommit_key.txt"),
    ]
    for cand in key_candidates:
        if os.path.isfile(cand):
            try:
                with open(cand, "r", encoding="utf-8") as f:
                    OPENAI_API_KEY = f.read().strip()
                break
            except Exception:
                pass

client = OpenAI(api_key=OPENAI_API_KEY)

st.set_page_config(page_title="PDF RAG System")
st.title("📄 PDF 기반 Q&A")
st.write(f"사용 가능한 GPU: {get_gpu_info()}")
model_name = st.selectbox("모델 선택", list(MODEL_OPTIONS.keys()))
model = MODEL_OPTIONS[model_name]
if model_name in ["llama-3", "mistral", "gemma"]:

    ensure_model(model)
st.write(f"사용 모델: {model_name}")

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


if "docs" not in st.session_state:
    st.session_state.docs = None
    st.session_state.embs = None
    st.session_state.pdf_text = ""

if "history" not in st.session_state:
    st.session_state.history = []


def cache_paths(filename: str):
    base = os.path.splitext(filename)[0]
    return {
        "pdf": os.path.join(DATA_DIR, filename),
        "txt": os.path.join(DATA_DIR, base + ".txt"),
        "npz": os.path.join(DATA_DIR, base + ".npz"),
        "base": base,
    }


def load_cached_data():
    """Load cached PDFs and embeddings into session_state."""
    st.session_state.docs = []
    st.session_state.embs = []
    st.session_state.pdf_text = ""
    st.session_state.cached_files = []
    for fname in sorted(os.listdir(DATA_DIR)):
        if not fname.endswith(".npz"):
            continue
        base = os.path.splitext(fname)[0]
        paths = cache_paths(base + ".pdf")
        data = np.load(paths["npz"], allow_pickle=True)
        chunks = data["chunks"].tolist()
        embs = data["embeddings"]
        st.session_state.docs.extend(chunks)
        st.session_state.embs.extend(embs)
        txt_path = paths["txt"]
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8") as f:
                st.session_state.pdf_text += f.read() + "\n"
        st.session_state.cached_files.append(base)


def save_pdf_and_embeddings(uploaded_file):
    paths = cache_paths(uploaded_file.name)
    if os.path.exists(paths["npz"]):
        return
    with open(paths["pdf"], "wb") as f:
        f.write(uploaded_file.getbuffer())
    text = read_pdf(paths["pdf"])
    with open(paths["txt"], "w", encoding="utf-8") as f:
        f.write(text)
    chunks = chunk_text(text)
    embs = []
    for chunk in chunks:
        resp = client.embeddings.create(model="text-embedding-3-small", input=[chunk])
        embs.append(np.array(resp.data[0].embedding))
    np.savez(paths["npz"], chunks=np.array(chunks, dtype=object), embeddings=np.array(embs))


def refresh_cache(selected_files):
    for name in selected_files:
        base = os.path.splitext(name)[0]
        paths = cache_paths(name)
        if os.path.exists(paths["pdf"]):
            text = read_pdf(paths["pdf"])
            with open(paths["txt"], "w", encoding="utf-8") as f:
                f.write(text)
            chunks = chunk_text(text)
            embs = []
            for chunk in chunks:
                resp = client.embeddings.create(
                    model="text-embedding-3-small", input=[chunk]
                )
                embs.append(np.array(resp.data[0].embedding))
            np.savez(
                paths["npz"],
                chunks=np.array(chunks, dtype=object),
                embeddings=np.array(embs),
            )


load_cached_data()


def read_pdf(file) -> str:
    text = ""
    reader = PdfReader(file)
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text


def chunk_text(text: str, chunk_size: int = 200, overlap: int = 50):
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        chunk = " ".join(words[start : start + chunk_size])
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks



uploaded_files = st.file_uploader(
    "PDF 업로드", type="pdf", accept_multiple_files=True
)
mode = st.radio("답변 모드", ["기본", "PDF 사용"])

if uploaded_files:
    st.subheader("업로드된 파일")
    total_size = sum(f.size for f in uploaded_files)
    st.write(f"총 {len(uploaded_files)}개 파일, {total_size / 1024:.1f} KB")
    for uf in uploaded_files:
        st.write(f"- {uf.name} ({uf.size / 1024:.1f} KB)")

    texts = []
    all_chunks = []
    for uf in uploaded_files:
        text = read_pdf(uf)
        texts.append(text)
        all_chunks.extend(chunk_text(text))
    st.session_state.pdf_text = "\n\n".join(texts)
    st.session_state.docs = all_chunks
    st.session_state.embs = []
    with st.spinner("임베딩 생성 중..."):
        for chunk in st.session_state.docs:
            resp = client.embeddings.create(
                model="text-embedding-3-small",
                input=[chunk],
            )
            st.session_state.embs.append(np.array(resp.data[0].embedding))

    st.success("문서 로딩 완료")

if st.session_state.get("cached_files"):
    st.subheader("캐시된 PDF")
    options = [f + ".pdf" for f in st.session_state.cached_files]
    selected = st.multiselect("캐시 파일 선택", options)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("선택 삭제") and selected:
            for name in selected:
                paths = cache_paths(name)
                for ext in ("pdf", "txt", "npz"):
                    p = paths[ext]
                    if os.path.exists(p):
                        os.remove(p)
            load_cached_data()
            st.success("삭제 완료")
    with c2:
        if st.button("선택 새로고침") and selected:
            refresh_cache(selected)
            load_cached_data()
            st.success("새로고침 완료")

st.markdown("---")
if st.session_state.history:
    options = [f"{i+1}. {h['question']}" for i, h in enumerate(st.session_state.history)]
    sel = st.selectbox("이전 질문 선택", [""] + options)
    if sel:
        idx = int(sel.split(".")[0]) - 1
        hist = st.session_state.history[idx]
        st.write(f"**질문:** {hist['question']}")
        st.write(f"**기본 답변:** {hist['answer']}")
        if hist.get("pdf_answer"):
            st.write(f"**PDF 답변:** {hist['pdf_answer']}")
        st.write(f"**응답 시간:** {hist['elapsed']:.2f}초")

question = st.text_input("질문 입력")

if question:
    default_box = st.container()
    pdf_box = st.container()
    text_box = st.container()

    with default_box:
        st.subheader("1. 기본 답변")
        with st.spinner("답변 생성 중..."):
            start_t = time.perf_counter()
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": question}],
                )
            except BadRequestError as e:
                log_error(str(e))
                reset_app()

            elapsed_default = time.perf_counter() - start_t
            default_answer = resp.choices[0].message.content
            st.write(default_answer)
            st.write(f"⏱️ {elapsed_default:.2f}초")

    with pdf_box:
        st.subheader("2. PDF 기반 답변")
        pdf_answer = None
        elapsed_pdf = None
        if mode == "PDF 사용":
            if st.session_state.docs:
                with st.spinner("답변 생성 중..."):
                    q_emb = np.array(
                        client.embeddings.create(
                            model="text-embedding-3-small", input=[question]
                        ).data[0].embedding
                    )
                    sims = [
                        float(
                            np.dot(q_emb, e)
                            / (np.linalg.norm(q_emb) * np.linalg.norm(e))
                        )
                        for e in st.session_state.embs
                    ]
                    top_indices = np.argsort(sims)[-3:][::-1]
                    context = "\n\n".join(
                        st.session_state.docs[i] for i in top_indices
                    )
                    prompt = (
                        "다음 문서 내용을 참고하여 질문에 답변하세요.\n\n문서 내용:\n"
                        + context
                        + "\n\n질문: "
                        + question
                    )
                    start_pdf = time.perf_counter()
                    try:
                        resp = client.chat.completions.create(
                            model=model,
                            messages=[{"role": "user", "content": prompt}],
                        )
                    except BadRequestError as e:
                        log_error(str(e))
                        reset_app()

                    elapsed_pdf = time.perf_counter() - start_pdf
                    pdf_answer = resp.choices[0].message.content
                    st.write(pdf_answer)
                    st.write(f"⏱️ {elapsed_pdf:.2f}초")

            else:
                st.warning("먼저 PDF 파일을 업로드하세요.")

    with text_box:
        st.subheader("3. PDF 내용")
        if st.session_state.pdf_text:
            st.text_area("", st.session_state.pdf_text, height=300)

    entry = {
        "question": question,
        "answer": default_answer,
        "elapsed": elapsed_default,
    }
    if pdf_answer:
        entry["pdf_answer"] = pdf_answer
        entry["pdf_elapsed"] = elapsed_pdf
    st.session_state.history.append(entry)
    if len(st.session_state.history) > 100:
        st.session_state.history.pop(0)

if st.session_state.history:
    col1, col2 = st.columns(2)
    with col1:
        if st.button("모든 Q&A 엑셀 저장"):
            df = pd.DataFrame(st.session_state.history)
            excel_io = io.BytesIO()
            df.to_excel(excel_io, index=False)
            st.download_button(
                "엑셀 다운로드",
                excel_io.getvalue(),
                file_name="qa_history.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    with col2:
        if st.button("모든 Q&A PDF 저장"):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            for item in st.session_state.history:
                text = f"Q: {item['question']}\nA: {item['answer']}\n"
                if item.get('pdf_answer'):
                    text += f"PDF: {item['pdf_answer']}\n"
                pdf.multi_cell(0, 10, txt=text)
                pdf.ln()
            pdf_io = io.BytesIO(pdf.output(dest="S").encode("latin-1"))
            st.download_button(
                "PDF 다운로드",
                pdf_io.getvalue(),
                file_name="qa_history.pdf",
                mime="application/pdf",
            )

if st.session_state.errors:
    st.markdown("---")
    st.subheader("에러 메시지")
    for err in st.session_state.errors[-3:]:
        st.error(err)
