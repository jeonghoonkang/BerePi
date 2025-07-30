import os
import re
from typing import List, Dict

import streamlit as st
import base64
import numpy as np


try:
    import openai
except Exception:
    openai = None

NOCOMMIT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "receipt_ocr/nocommit"
)
os.makedirs(NOCOMMIT_DIR, exist_ok=True)

OPENAI_KEY_PATH = os.path.join(NOCOMMIT_DIR, "nocommit_key.txt")

openai_api_key = None
if os.path.exists(OPENAI_KEY_PATH):
    with open(OPENAI_KEY_PATH) as f:
        openai_api_key = f.read().strip()
else:
    st.error(OPENAI_KEY_PATH)
    st.error("OpenAI API key not found in nocommit/nocommit_key.txt")

if openai and openai_api_key:
    openai.api_key = openai_api_key

if openai is None:
    st.error("openai package is not installed")


AMOUNT_REGEX = re.compile(r"([\d,.]+)")
ADDRESS_KEYWORDS = ["Address", "주소"]


def extract_amount(text: str) -> int:
    """Extract the first integer-like value from text."""
    matches = AMOUNT_REGEX.findall(text)
    for m in matches[::-1]:  # try from last to handle typical layout
        cleaned = m.replace(",", "").replace(".", "")
        if cleaned.isdigit():
            return int(cleaned)
    return 0


def extract_address(text: str) -> str:
    lines = text.splitlines()
    for line in lines:
        if any(k.lower() in line.lower() for k in ADDRESS_KEYWORDS):
            return line.strip()
    return "Unknown"





def openai_ocr_image(path: str) -> str:
    if openai is None or openai_api_key is None:
        return ""
    with open(path, "rb") as f:
        img_bytes = f.read()
    encoded = base64.b64encode(img_bytes).decode("utf-8")
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Please transcribe all text from this receipt image.",
                        },
                        {"type": "image_url", "image_url": {"data": encoded}},
                    ],
                }
            ],

            max_tokens=2000,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return ""


def create_embedding(text: str):
    if openai is None or openai_api_key is None:
        return []
    try:
        resp = openai.embeddings.create(
            model="text-embedding-3-small", input=[text]
        )
        return resp.data[0].embedding
    except Exception:
        return []


def embed_receipts(receipts: List[Dict]):
    for r in receipts:
        emb = create_embedding(r["text"])
        if emb:
            r["embedding"] = np.array(emb)


def rag_answer(question: str, receipts: List[Dict]) -> str:
    if openai is None or openai_api_key is None:
        return ""
    q_emb_list = create_embedding(question)
    if not q_emb_list:
        return ""
    q_emb = np.array(q_emb_list)
    scored = []
    for r in receipts:
        emb = r.get("embedding")
        if emb is None:
            continue
        sim = float(np.dot(q_emb, emb) / (np.linalg.norm(q_emb) * np.linalg.norm(emb)))
        scored.append((sim, r))
    if not scored:
        return ""
    scored.sort(key=lambda x: x[0], reverse=True)
    top_receipts = [r for _, r in scored[:3]]
    context = "\n\n".join(f"{r['filename']}:\n{r['text']}" for r in top_receipts)
    prompt = (
        "다음 영수증 내용을 참고하여 질문에 답변하세요.\n\n" + context + "\n\n질문: " + question
    )
    try:
        resp = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return ""

def process_receipts(files: List[Dict]) -> List[Dict]:
    receipts = []
    for file in files:
        save_path = os.path.join(NOCOMMIT_DIR, file.name)
        with open(save_path, "wb") as out:
            out.write(file.getbuffer())
        text = openai_ocr_image(save_path)
        amount = extract_amount(text)
        address = extract_address(text)
        receipts.append(
            {
                "filename": file.name,
                "text": text,
                "amount": amount,
                "address": address,
                "path": save_path,
            }
        )

    return receipts


def summarize(receipts: List[Dict]):
    total = sum(r["amount"] for r in receipts)
    st.write(f"**총 금액 합계: {total}**")
    grouped: Dict[str, List[Dict]] = {}
    for r in receipts:
        grouped.setdefault(r["address"], []).append(r)
    for addr, items in grouped.items():
        st.subheader(addr)
        for item in items:
            st.write(f"{item['filename']}: {item['amount']}")


st.title("Receipt OCR")
uploaded_files = st.file_uploader(
    "영수증 스캔 파일 업로드 (여러개 선택 가능)",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True,
)

if uploaded_files:

    receipts = process_receipts(uploaded_files)
    embed_receipts(receipts)
    summarize(receipts)
    st.header("OCR 결과")
    for r in receipts:
        st.subheader(r["filename"])
        st.text(r["text"])

    question = st.text_input("질문을 입력하세요")
    if question:
        answer = rag_answer(question, receipts)
        if answer:
            st.write(answer)
        else:
            st.write("답변을 생성하지 못했습니다.")

    st.header("원본 이미지")
    for r in receipts:
        st.subheader(r["filename"])
        st.image(r["path"], use_column_width=True)

