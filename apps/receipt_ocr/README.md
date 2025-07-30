# Receipt OCR Streamlit App

This Streamlit app lets you upload many receipt images and uses OpenAI's GPT‑4 Vision
to extract text from each one. Uploaded files are saved in the `nocommit` directory,
which is ignored by git. Amounts found in each receipt are summed and receipts are
grouped by detected address. The original images are shown at the bottom of the page.

Place your OpenAI API key in `nocommit/nocommit_key.txt` before running the app. You
can ask questions like "금액 합계" or "주소별 합계" in the question box.
## Usage
```
streamlit run apps/receipt_ocr/receipt_ocr_app.py
```
