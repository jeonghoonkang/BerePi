# Qwen Streamlit Demo

This example shows how to build a simple chat interface using [Streamlit](https://streamlit.io/) and the Qwen language model from HuggingFace.

## Requirements

Install the required Python packages:

```bash
pip install streamlit transformers torch
```

## Usage

Run the Streamlit application:

```bash
streamlit run app.py
```

The application will automatically download the `Qwen/Qwen1.5-0.5B-Chat` model
on first run if it is not available locally. When this happens the program
prints a progress bar in the terminal using the **rich** library and the
Streamlit UI will only appear once the download finishes. After the model is
ready, enter a sentence in the text input box and the model will generate a
response.
