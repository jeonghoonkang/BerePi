# Receipt OCR Streamlit App

This Streamlit app lets you upload many receipt images or PDF documents and uses
OpenAI's GPT‑4o model to extract text from each one. The OCR prompt is tuned for
Korean so Hangul is transcribed accurately. Uploaded files are saved in the
`nocommit` directory, which is ignored by git. Amounts found in each receipt are
summed and receipts are grouped by detected address. The original files are shown
at the bottom of the page.

Place your OpenAI API key in `nocommit/nocommit_key.txt` before running the app.
After OCR extraction embeddings are built with the `text-embedding-3-large` model
and a retrieval augmented generation (RAG) pipeline lets you ask questions like
"금액 합계" or "주소별 합계" in the question box.

## Usage
```
streamlit run apps/receipt_ocr/receipt_ocr_app.py
```
