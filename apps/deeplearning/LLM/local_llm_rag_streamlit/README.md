# Local LLM RAG Streamlit

Streamlit interface for running a Retrieval-Augmented Generation (RAG) pipeline on top of a local LLM.  

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
