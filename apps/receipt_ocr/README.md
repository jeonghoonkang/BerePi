# Receipt OCR Streamlit App

This Streamlit app lets you upload many receipt images or PDF documents and uses
OpenAI's GPT‑4o model to extract text from each one. The OCR prompt is tuned for
Korean so Hangul is transcribed accurately. Uploaded files are saved in the
`nocommit` directory, which is ignored by git. Amounts found in each receipt are
summed and receipts are grouped by detected address. The original files can be
reviewed one at a time with arrow buttons instead of a long list. The recognized
text is stored for Q&A but not displayed next to the images. Each image is
Base64 encoded before being sent to OpenAI for OCR.
During the upload a progress bar inside the Streamlit app shows the status of
files being sent to OpenAI.
Uploaded receipts are cached so subsequent Q&A uses the stored text without
re-uploading, and each answer shows how long the model took to respond.

Place your OpenAI API key in `nocommit/nocommit_key.txt` before running the app.
After OCR extraction embeddings are built with the `text-embedding-3-large` model
and a retrieval augmented generation (RAG) pipeline powers a Q&A chat box so you
can ask questions like "금액 합계" or "주소별 합계" about the recognized text.

## Usage
```
streamlit run apps/receipt_ocr/receipt_ocr_app.py
```
