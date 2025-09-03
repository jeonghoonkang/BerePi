
import json
import time
from pathlib import Path

import streamlit as st
from PIL import Image
from pdf2image import convert_from_path
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from rich.console import Console

from llama_index import Document, VectorStoreIndex, ServiceContext
from llama_index.llms import HuggingFaceLLM


# Base directories
BASE_DIR = Path(__file__).resolve().parents[2]
DOCS_DIR = BASE_DIR / "documents"

console = Console()


@st.cache_resource
def load_ocr_model():
    """Load TrOCR model and processor."""
    processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-printed")
    model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-printed")
    return processor, model


def ocr_image(img, processor, model):
    """Run OCR on a PIL image and return text."""
    pixel_values = processor(images=img, return_tensors="pt").pixel_values
    output_ids = model.generate(pixel_values)
    text = processor.batch_decode(output_ids, skip_special_tokens=True)[0]
    return text


def ocr_pdf(path, processor, model):
    """Run OCR on each page of a PDF file."""
    images = convert_from_path(path)
    texts = [ocr_image(img, processor, model) for img in images]
    return "\n".join(texts)


def run_ocr():
    """OCR all PDF/JPG files inside documents folder."""
    processor, model = load_ocr_model()
    data = []
    for file in DOCS_DIR.glob("*"):
        ext = file.suffix.lower()
        if ext in [".jpg", ".jpeg", ".png"]:
            text = ocr_image(Image.open(file), processor, model)
        elif ext == ".pdf":
            text = ocr_pdf(file, processor, model)
        else:
            continue
        sentences = [s.strip() for s in text.replace("\n", " ").split('.') if s.strip()]
        data.append({"file_name": file.name, "text": text, "sentences": sentences})
    return data


def build_query_engine(data):
    """Build a LlamaIndex query engine using KULLM model."""
    documents = [Document(d["text"], metadata={"file": d["file_name"]}) for d in data]
    llm = HuggingFaceLLM(model_name="circulus/KULLM-Polyglot-12.8B-v2", max_new_tokens=256)
    service_context = ServiceContext.from_defaults(llm=llm)
    index = VectorStoreIndex.from_documents(documents, service_context=service_context)
    return index.as_query_engine()


st.title("TrOCR 기반 RAG Q&A")

uploaded = st.file_uploader("PDF 혹은 이미지 파일 업로드", type=["pdf", "jpg", "jpeg", "png"])
if uploaded is not None:
    if st.button("documents 폴더에 저장"):
        save_path = DOCS_DIR / uploaded.name
        with open(save_path, "wb") as f:
            f.write(uploaded.getbuffer())
        st.success(f"{uploaded.name} 저장 완료")

if st.button("OCR 실행"):
    st.session_state["ocr_data"] = run_ocr()
    st.success("OCR 완료")

if "ocr_data" in st.session_state:
    with st.expander("OCR 결과 (JSON)", expanded=False):
        st.json(st.session_state["ocr_data"])

    if st.button("JSON 저장"):
        json_path = DOCS_DIR / "ocr_output.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(st.session_state["ocr_data"], f, ensure_ascii=False, indent=2)
        st.success(f"저장 완료: {json_path}")

    query_engine = build_query_engine(st.session_state["ocr_data"])
    question = st.text_input("질문 입력")
    if st.button("질문하기") and question:
        start = time.time()
        response = query_engine.query(question)
        elapsed = time.time() - start
        st.write(response.response)
        st.write(f"응답 시간: {elapsed:.2f}초")
        console.print(f"Q: {question}\nA: {response.response}\nTime: {elapsed:.2f}s", style="bold green")
