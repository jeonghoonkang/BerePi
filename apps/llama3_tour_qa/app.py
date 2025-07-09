import os
import streamlit as st
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

st.set_page_config(page_title="Korean Tourism Q&A", page_icon="\ud83c\udf0d")

st.title("\ud83c\uddf0\ud83c\uddf7 Korean Tourism Q&A with Llama 3")

# Load model only once
@st.cache_resource
def load_model():
    model_name = os.environ.get("LLAMA3_MODEL", "meta-llama/Meta-Llama-3-8B-Instruct")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name)
    generator = pipeline("text-generation", model=model, tokenizer=tokenizer)
    return generator

generator = load_model()

prompt = st.text_input("Ask about tourism in Korea:")
if prompt:
    with st.spinner("Generating answer..."):
        # We limit max length to keep response quick
        response = generator(prompt, max_length=512, do_sample=True)
        st.write(response[0]["generated_text"][len(prompt):].strip())
