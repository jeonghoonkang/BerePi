import os
import re
from typing import List, Dict

import streamlit as st
from PIL import Image, ImageOps

try:
    import pytesseract
except Exception as e:
    pytesseract = None
    st.error("pytesseract is not installed. OCR functionality will not work.")

NOCOMMIT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nocommit")
os.makedirs(NOCOMMIT_DIR, exist_ok=True)

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


def ocr_image(path: str) -> str:
    if pytesseract is None:
        return ""
    img = Image.open(path)
    # improve OCR accuracy on Korean text
    img = img.convert("L")
    img = ImageOps.invert(img)
    img = img.point(lambda x: 0 if x < 150 else 255, "1")
    return pytesseract.image_to_string(img, lang="kor+eng", config="--psm 6")


def process_receipts(files: List[Dict]) -> List[Dict]:
    receipts = []
    for file in files:
        save_path = os.path.join(NOCOMMIT_DIR, file.name)
        with open(save_path, "wb") as out:
            out.write(file.getbuffer())
        text = ocr_image(save_path)
        amount = extract_amount(text)
        address = extract_address(text)
        receipts.append({
            "filename": file.name,
            "text": text,
            "amount": amount,
            "address": address,
            "path": save_path,
        })
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
    if len(uploaded_files) > 10:
        st.warning("최대 10개 파일만 처리합니다. 일부만 사용합니다.")
        uploaded_files = uploaded_files[:10]
    receipts = process_receipts(uploaded_files)
    summarize(receipts)
    with st.expander("세부 내용 보기"):
        for r in receipts:
            st.write(f"### {r['filename']}")
            st.text(r['text'])
    st.header("원본 이미지")
    for r in receipts:
        st.subheader(r["filename"])
        st.image(r["path"], use_column_width=True)
