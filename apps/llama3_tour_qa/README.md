# Korean Tourism Q&A with Llama 3

This Streamlit app uses Meta's Llama 3 model to answer questions about travel in Korea.

## Usage

1. Install requirements:
   ```bash
   pip install streamlit transformers huggingface_hub

   ```
   You also need a local copy of the Llama 3 model. Set the environment variable `LLAMA3_MODEL` to the directory or model name.
2. Run the app:
   ```bash
   streamlit run app.py
   ```

By default the app loads `meta-llama/Meta-Llama-3-8B-Instruct` from HuggingFace.
Set `LLAMA3_MODEL` if you want to use a local path or a different model. If the model files are missing, the app will prompt you to download them and automatically start after 10 seconds, showing a progress bar while downloading.

