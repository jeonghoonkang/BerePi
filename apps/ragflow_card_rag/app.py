import os
import base64

import streamlit as st
from openai import OpenAI

try:
    from ragflow import RAGFlow  # pragma: no cover
except Exception:  # ragflow not installed
    from ragflow_card_rag.ragflow_simple import SimpleRAGFlow as RAGFlow  # type: ignore


def load_api_key() -> str:
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key
    candidates = [
        os.path.join(os.path.dirname(__file__), "nocommit", "nocommit_key.txt"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "nocommit", "nocommit_key.txt"),
    ]
    for cand in candidates:
        if os.path.isfile(cand):
            try:
                with open(cand, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                continue
    return ""


def ocr_image(client: OpenAI, image_bytes: bytes) -> str:
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    resp = client.responses.create(
        model="gpt-4o-mini",
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Extract all text from this business card image."},
                    {"type": "input_image", "image": b64},
                ],
            }
        ],
    )
    try:
        return resp.output[0].content[0].text.strip()
    except Exception:
        # Fallback for older clients
        return resp.output_text.strip() if hasattr(resp, "output_text") else ""


API_KEY = load_api_key()
client = OpenAI(api_key=API_KEY)

st.set_page_config(page_title="Business Card RAG")
st.title("📇 명함 OCR RAG (RAGFlow)")

if "rag" not in st.session_state:
    st.session_state.rag = RAGFlow(client)

uploaded = st.file_uploader("명함 이미지 업로드", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded:
    for uf in uploaded:
        text = ocr_image(client, uf.read())
        if text:
            st.session_state.rag.add_document(text)
            st.success(f"{uf.name} 처리 완료")
        else:
            st.warning(f"{uf.name} 에서 텍스트를 추출하지 못했습니다")

st.markdown("---")
question = st.text_input("질문을 입력하세요")
if question:
    answer = st.session_state.rag.query(question)
    st.write("**답변:**", answer)
