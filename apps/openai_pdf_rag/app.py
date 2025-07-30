import os
import io
import numpy as np
import streamlit as st
from openai import OpenAI
from PyPDF2 import PdfReader

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

st.set_page_config(page_title="PDF RAG Chat")
st.title("📄 PDF 기반 Q&A")

if "docs" not in st.session_state:
    st.session_state.docs = None
    st.session_state.embs = None


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


uploaded_file = st.file_uploader("PDF 업로드", type="pdf")

if uploaded_file:
    text = read_pdf(uploaded_file)
    st.session_state.docs = chunk_text(text)
    st.session_state.embs = []
    with st.spinner("임베딩 생성 중..."):
        for chunk in st.session_state.docs:
            resp = client.embeddings.create(
                model="text-embedding-3-small",
                input=[chunk],
            )
            st.session_state.embs.append(np.array(resp.data[0].embedding))
    st.success("문서 로딩 완료")

question = st.text_input("질문 입력")
if question and st.session_state.docs:
    with st.spinner("답변 생성 중..."):
        q_emb = np.array(
            client.embeddings.create(
                model="text-embedding-3-small", input=[question]
            ).data[0].embedding
        )
        sims = [
            float(np.dot(q_emb, e) / (np.linalg.norm(q_emb) * np.linalg.norm(e)))
            for e in st.session_state.embs
        ]
        top_indices = np.argsort(sims)[-3:][::-1]
        context = "\n\n".join(st.session_state.docs[i] for i in top_indices)
        prompt = (
            "다음 문서 내용을 참고하여 질문에 답변하세요.\n\n문서 내용:\n"
            + context
            + "\n\n질문: "
            + question
        )
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
        )
        st.write(resp.choices[0].message.content)
