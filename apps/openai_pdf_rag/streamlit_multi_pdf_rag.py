import subprocess
import os
from typing import List

import numpy as np
import streamlit as st
import ollama
from PyPDF2 import PdfReader


st.set_page_config(page_title="PDF RAG Chat")
st.title("📄 PDF RAG Chat")

# 현재 설치된 모델 목록을 가져와 선택 박스에 표시
available_models = [m["name"] for m in ollama.list().get("models", [])]

# RAG에 사용할 생성 모델, 임베딩 모델, 일반 QA 모델을 각각 지정
rag_model = (
    st.selectbox("RAG 생성 모델", options=available_models)
    if available_models
    else st.text_input("RAG 생성 모델 이름")
)
embed_models = [m for m in available_models if "embed" in m]
embed_model = (
    st.selectbox("임베딩 모델", options=embed_models)
    if embed_models
    else st.text_input("임베딩 모델 이름", "nomic-embed-text")
)
direct_model = (
    st.selectbox("일반 QA 모델", options=available_models)
    if available_models
    else st.text_input("일반 QA 모델 이름")
)

st.caption(f"RAG 모델: {rag_model} | 일반 모델: {direct_model}")

st.markdown("### OSS 모델 다운로드")
model_to_pull = st.text_input("모델 이름 입력")
if st.button("모델 다운로드") and model_to_pull:
    with st.spinner("모델 다운로드 중..."):
        result = subprocess.run(
            ["ollama", "pull", model_to_pull], capture_output=True, text=True
        )
    if result.returncode == 0:
        st.success("다운로드 완료")
    else:
        st.error(result.stderr or "다운로드 실패")


uploaded_files = st.file_uploader(
    "PDF 파일을 업로드하세요", type="pdf", accept_multiple_files=True
)

# 보여줄 파일 목록
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


# 문서에서 추출한 텍스트를 쪼개고 임베딩 생성
all_chunks: List[str] = []
embeddings: List[np.ndarray] = []
if uploaded_files:
    for uf in uploaded_files:
        pdf_text = read_pdf(uf)
        all_chunks.extend(split_text(pdf_text))

    with st.spinner("임베딩 생성 중..."):
        for chunk in all_chunks:
            emb = ollama.embeddings(model=embed_model, prompt=chunk)["embedding"]

            embeddings.append(np.array(emb))
    st.success("임베딩 생성 완료")

st.markdown("---")
question = st.text_input("질문을 입력하세요")

if question:
    # RAG 기반 답변
    if embeddings:
        q_emb = ollama.embeddings(model=embed_model, prompt=question)["embedding"]
        q_emb = np.array(q_emb)

        sims = [
            float(np.dot(q_emb, e) / (np.linalg.norm(q_emb) * np.linalg.norm(e)))
            for e in embeddings
        ]
        top_indices = np.argsort(sims)[-3:][::-1]
        context = "\n\n".join(all_chunks[i] for i in top_indices)

        prompt = (
            "다음 문서 내용을 참고하여 질문에 답변하세요.\n\n" + context + "\n\n질문: " + question
        )
        with st.spinner("RAG 답변 생성 중..."):
            completion = ollama.generate(model=rag_model, prompt=prompt)
            rag_answer = completion.get("response", "")
        st.text_area("RAG 답변", rag_answer, height=200)
    else:
        st.warning("먼저 PDF 파일을 업로드하세요.")

    # 비 RAG 일반 답변
    with st.spinner("일반 답변 생성 중..."):
        direct_completion = ollama.generate(model=direct_model, prompt=question)
        direct_answer = direct_completion.get("response", "")
    st.text_area("일반 모델 답변", direct_answer, height=200)

