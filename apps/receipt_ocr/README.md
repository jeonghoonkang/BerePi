# Receipt OCR Streamlit App

This app lets you upload receipt images and extract text using OCR. Up to 10 files
can be processed. Uploaded files are saved in the `nocommit` directory, which is
ignored by git. Amounts found in each receipt are summed and receipts are grouped
by detected address. The app now displays the uploaded images at the bottom of the
page and applies simple preprocessing to improve Korean text recognition.

## Usage
```
streamlit run apps/receipt_ocr/receipt_ocr_app.py
```
Place your OpenAI API key in `nocommit/openai_key.txt` if you plan to extend the
app with OpenAI features.
