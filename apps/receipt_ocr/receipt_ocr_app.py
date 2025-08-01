import os
import re
from typing import List, Dict

import streamlit as st
import base64
import numpy as np
import time
import json


try:
    import openai
except Exception:
    openai = None

NOCOMMIT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "receipt_ocr/nocommit"
)
os.makedirs(NOCOMMIT_DIR, exist_ok=True)

# Directory to store uploaded images shown in the viewer
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "upload")
os.makedirs(UPLOAD_DIR, exist_ok=True)

OCR_JSON_PATH = os.path.join(NOCOMMIT_DIR, "ocr_results.json")

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


def encode_file_to_base64(path: str) -> str:
    """Read a file and return a base64-encoded string."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")



def openai_ocr_file(path: str) -> str:
    """Send an image or PDF to GPT-4o for OCR."""
    if openai is None or openai_api_key is None:
        return ""
    ext = os.path.splitext(path)[1].lower()
    b64 = encode_file_to_base64(path)
    if ext in [".png", ".jpg", ".jpeg", ".webp"]:
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(ext, "application/octet-stream")
        data_url = f"data:{mime};base64,{b64}"
        content = [
            {
                "type": "text",
                "text": "이 문서에 포함된 모든 글자를 가능한 한 정확하게 한국어로 전사해 주세요.",
            },
            {"type": "image_url", "image_url": {"url": data_url}},
        ]
    else:
        content = [
            {
                "type": "text",
                "text": "이 문서에 포함된 모든 글자를 가능한 한 정확하게 한국어로 전사해 주세요.",
            },
            {"type": "file", "file": {"data": b64, "mime_type": "application/pdf"}},
        ]
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You accurately transcribe Korean text from documents.",
                },
                {"role": "user", "content": content},
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
            model="text-embedding-3-large", input=[text]
        )
        return resp.data[0].embedding
    except Exception:
        return []


def embed_receipts(receipts: List[Dict]):
    for r in receipts:
        if r.get("embedding") is None:
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
            messages=[
                {
                    "role": "system",
                    "content": "Answer in Korean using the provided receipts as context.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return ""


def merge_save_ocr_json(new_receipts: List[Dict], path: str = OCR_JSON_PATH):
    existing: List[Dict] = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = []
    data = {r.get("filename"): r for r in existing if r.get("filename")}
    for r in new_receipts:
        data[r.get("filename")] = r
    with open(path, "w", encoding="utf-8") as f:
        json.dump(list(data.values()), f, ensure_ascii=False, indent=2)


def init_existing_receipts():
    if "receipts" in st.session_state:
        return
    receipts: List[Dict] = []
    if os.path.exists(OCR_JSON_PATH):
        try:
            with open(OCR_JSON_PATH, "r", encoding="utf-8") as f:
                receipts = json.load(f)
        except Exception:
            receipts = []

    data: Dict[str, Dict] = {r.get("filename"): r for r in receipts if r.get("filename")}
    new_receipts: List[Dict] = []


    for fname in os.listdir(UPLOAD_DIR):
        path = os.path.join(UPLOAD_DIR, fname)
        if not os.path.isfile(path):
            continue
        if os.path.splitext(fname)[1].lower() not in [
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".pdf",
        ]:
            continue
        rec = data.get(fname)
        if rec is None or not rec.get("text"):
            text = openai_ocr_file(path)
            amount = extract_amount(text)
            address = extract_address(text)
            rec = {
                "filename": fname,
                "text": text,
                "amount": amount,
                "address": address,
                "path": path,
            }
            data[fname] = rec
            new_receipts.append(rec)
        else:
            rec["path"] = path

    receipts = list(data.values())
    if new_receipts:
        merge_save_ocr_json(new_receipts)
    for r in receipts:
        r.setdefault("path", os.path.join(UPLOAD_DIR, r["filename"]))

    embed_receipts(receipts)
    st.session_state.receipts = receipts
    st.session_state.uploaded_names = [r["filename"] for r in receipts]

def process_receipts(files: List[Dict]) -> List[Dict]:
    receipts: List[Dict] = []
    status = st.empty()
    bar = st.progress(0)
    total = len(files)
    for i, file in enumerate(files, start=1):
        status.text(f"{file.name} 업로드 중")
        bar.progress((i - 1) / total)
        save_path = os.path.join(UPLOAD_DIR, file.name)
        with open(save_path, "wb") as out:
            out.write(file.getbuffer())
        text = openai_ocr_file(save_path)
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
        bar.progress(i / total)
    status.text("완료")
    if receipts:
        merge_save_ocr_json(receipts)
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
init_existing_receipts()
uploaded_files = st.file_uploader(
    "영수증 스캔 파일 업로드 (여러개 선택 가능)",
    type=["png", "jpg", "jpeg", "webp", "pdf"],
    accept_multiple_files=True,
)

if uploaded_files:
    new_receipts = process_receipts(uploaded_files)
    embed_receipts(new_receipts)
    if "receipts" in st.session_state:
        st.session_state.receipts.extend(new_receipts)
    else:
        st.session_state.receipts = new_receipts
    st.session_state.uploaded_names = [r["filename"] for r in st.session_state.receipts]

receipts = st.session_state.get("receipts", [])

if receipts:

    with st.expander("process_receipts 결과", expanded=False):
        st.json(receipts)
    summarize(receipts)


    st.header("영수증 이미지")
    if "view_idx" not in st.session_state:
        st.session_state.view_idx = 0
    if "file_name" not in st.session_state:
        st.session_state.file_name = receipts[0]["filename"]

    file_name = st.text_input("파일 이름", st.session_state.file_name)
    path = os.path.join(UPLOAD_DIR, file_name)
    if os.path.exists(path):
        st.session_state.file_name = file_name
        idx = next((i for i, r in enumerate(receipts) if r["filename"] == file_name), None)
        if idx is not None:
            st.session_state.view_idx = idx
        st.image(path, use_column_width=True)
    else:
        st.warning("해당 파일이 없습니다.")

    col1, _, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("◀", use_container_width=True):
            st.session_state.view_idx = (st.session_state.view_idx - 1) % len(receipts)
            st.session_state.file_name = receipts[st.session_state.view_idx]["filename"]
    with col3:
        if st.button("▶", use_container_width=True):
            st.session_state.view_idx = (st.session_state.view_idx + 1) % len(receipts)
            st.session_state.file_name = receipts[st.session_state.view_idx]["filename"]

    st.header("Q&A")
    if "qa_history" not in st.session_state:
        st.session_state.qa_history = []
    if question := st.chat_input("질문을 입력하세요"):
        st.session_state.qa_history.append({"role": "user", "content": question})
        start_t = time.time()
        answer = rag_answer(question, receipts)
        elapsed = time.time() - start_t
        st.session_state.qa_history.append(
            {
                "role": "assistant",
                "content": answer if answer else "답변을 생성하지 못했습니다.",
                "elapsed": elapsed,
            }
        )
    for msg in st.session_state.qa_history:
        with st.chat_message("user" if msg["role"] == "user" else "assistant"):
            st.write(msg["content"])
            if msg.get("elapsed") is not None:
                st.caption(f"응답 시간: {msg['elapsed']:.2f}초")

else:
    st.info("영수증이 없습니다. 파일을 업로드하세요.")

