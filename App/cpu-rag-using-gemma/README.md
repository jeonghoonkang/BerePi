# Local LLM RAG Streamlit

Streamlit interface for running a Retrieval-Augmented Generation (RAG) pipeline on top of a local LLM.

This variant is pinned to CPU execution so it can run on machines without a CUDA-capable GPU. All
model loading and inference are executed on the CPU regardless of hardware availability.

## Features
- Load an on-device LLM by providing its model path.
- Index all PDF files placed in the `docs/` directory.
- Upload additional PDFs via the web UI; uploaded files are saved to `docs/` and immediately indexed.
- Generate `file_list.txt` containing the list of indexed files and display it in the sidebar.
- Ask questions and receive answers along with the path to the most relevant PDF.

## Usage
```bash
streamlit run app.py
```

When prompted for the model path, provide a Gemma model directory that has been downloaded locally.
The application will load the model in `float32` precision on the CPU and serve the RAG workflow via
Streamlit.
