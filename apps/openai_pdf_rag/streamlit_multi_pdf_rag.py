import os
from typing import List

import numpy as np
import streamlit as st
from openai import OpenAI
from PyPDF2 import PdfReader


MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

client = OpenAI()

st.set_page_config(page_title="PDF RAG Chat")
st.title("📄 PDF RAG Chat")
st.caption(f"사용 모델: {MODEL_NAME}")

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
            emb = client.embeddings.create(
                model=EMBED_MODEL,
                input=[chunk],
            ).data[0].embedding
            embeddings.append(np.array(emb))
    st.success("임베딩 생성 완료")

st.markdown("---")
question = st.text_input("질문을 입력하세요")

if question and embeddings:
    q_emb = client.embeddings.create(
        model=EMBED_MODEL,
        input=[question],
    ).data[0].embedding
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
    with st.spinner("답변 생성 중..."):
        completion = client.responses.create(model=MODEL_NAME, input=prompt)
        answer = completion.output[0].content[0].text
    st.text_area("답변", answer, height=200)
elif question:
    st.warning("먼저 PDF 파일을 업로드하세요.")
