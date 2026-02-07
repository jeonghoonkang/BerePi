"""Streamlit app for local LLM RAG pipeline.
This app allows users to:
- Load a local LLM from a given path.
- Build a RAG pipeline on PDF documents stored in a directory.
- Upload additional PDFs which are automatically indexed.
- View the list of indexed files and save this list to a text file.
- Ask questions answered by the local LLM using relevant PDF context.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import streamlit as st
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS
from langchain.llms import HuggingFacePipeline
from langchain import PromptTemplate, LLMChain
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

# Directories
BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR / "docs"
VECTOR_STORE_DIR = BASE_DIR / "faiss_index"
FILE_LIST_PATH = BASE_DIR / "file_list.txt"

DOCS_DIR.mkdir(exist_ok=True)
VECTOR_STORE_DIR.mkdir(exist_ok=True)

# Utilities
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")


def build_file_list() -> List[Path]:
    """Return list of PDF files and write them to FILE_LIST_PATH."""
    files = sorted(DOCS_DIR.glob("*.pdf"))
    with open(FILE_LIST_PATH, "w", encoding="utf-8") as f:
        for file in files:
            f.write(str(file) + "\n")
    return files


def load_vector_store() -> FAISS | None:
    """Load existing FAISS index or create a new one from current PDFs."""
    if VECTOR_STORE_DIR.joinpath("index.faiss").exists():
        return FAISS.load_local(VECTOR_STORE_DIR, embeddings, allow_dangerous_deserialization=True)

    files = build_file_list()
    documents = []
    for pdf in files:
        loader = PyPDFLoader(str(pdf))
        documents.extend(text_splitter.split_documents(loader.load()))
    if not documents:
        return None
    vs = FAISS.from_documents(documents, embeddings)
    vs.save_local(VECTOR_STORE_DIR)
    return vs


def add_pdf_to_index(path: Path, vs: FAISS | None) -> FAISS:
    """Add a new PDF to the FAISS index."""
    loader = PyPDFLoader(str(path))
    docs = text_splitter.split_documents(loader.load())
    if vs is None:
        vs = FAISS.from_documents(docs, embeddings)
    else:
        vs.add_documents(docs)
    vs.save_local(VECTOR_STORE_DIR)
    return vs


# Streamlit session state
if "vector_store" not in st.session_state:
    st.session_state.vector_store = load_vector_store()

if "llm" not in st.session_state:
    st.session_state.llm = None

# Sidebar: show indexed files
st.sidebar.header("Indexed files")
for file_path in build_file_list():
    st.sidebar.write(str(file_path))

# Model loader
model_path = st.text_input("Path to local LLM model")
if model_path and st.session_state.llm is None:
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        model = AutoModelForCausalLM.from_pretrained(model_path, device_map="auto")
        pipe = pipeline("text-generation", model=model, tokenizer=tokenizer, max_new_tokens=512)
        st.session_state.llm = HuggingFacePipeline(pipeline=pipe)
        st.success("LLM loaded successfully")
    except Exception as e:  # pragma: no cover - runtime feedback
        st.error(f"Failed to load model: {e}")

# File uploader
uploaded = st.file_uploader("Upload PDF", type=["pdf"])
if uploaded is not None:
    save_path = DOCS_DIR / uploaded.name
    with open(save_path, "wb") as f:
        f.write(uploaded.getbuffer())
    st.session_state.vector_store = add_pdf_to_index(save_path, st.session_state.vector_store)
    st.experimental_rerun()

# Question input
question = st.text_input("Question")
if question and st.session_state.llm and st.session_state.vector_store:
    docs = st.session_state.vector_store.similarity_search(question, k=3)
    context = "\n\n".join(d.page_content for d in docs)
    prompt = PromptTemplate(
        input_variables=["context", "question"],
        template="Use the context below to answer the question.\n\nContext:\n{context}\n\nQuestion: {question}\nAnswer:",
    )
    chain = LLMChain(llm=st.session_state.llm, prompt=prompt)
    answer = chain.run(context=context, question=question)
    st.write("Answer:", answer)
    if docs:
        st.write("Most relevant document:", docs[0].metadata.get("source", "unknown"))
elif question and not st.session_state.llm:
    st.warning("Please load a local LLM model first.")
elif question and not st.session_state.vector_store:
    st.warning("No documents indexed yet.")
