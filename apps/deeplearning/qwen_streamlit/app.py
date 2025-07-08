import streamlit as st
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch


def load_model(model_name: str):
    """Load the tokenizer and model."""
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    return tokenizer, model, device


def generate_response(prompt: str, tokenizer, model, device):
    """Generate text from the model given a prompt."""
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model.generate(**inputs, max_new_tokens=128)
    return tokenizer.decode(outputs[0], skip_special_tokens=True)


st.title("Qwen Chat")
model_name = "Qwen/Qwen1.5-0.5B-Chat"

@st.cache_resource
def get_model():
    return load_model(model_name)


prompt = st.text_input("Enter a sentence")
if prompt:
    tokenizer, model, device = get_model()
    response = generate_response(prompt, tokenizer, model, device)
    st.write(response)
