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

The application lets you choose between the lightweight `Qwen1.5-0.5B-Chat`
and the larger `Qwen1.5-1.8B-Chat (GGUF)` model. The selected model is
downloaded automatically on first run, showing a progress bar in the terminal
via the **rich** library. The Streamlit UI only appears after the download
completes. After the model is ready, enter a sentence (look for the person
emoji next to the input field) and the robot emoji will display the response.
If PyTorch detects the MPS backend (for Apple Silicon), the app will use it
automatically for faster inference.
