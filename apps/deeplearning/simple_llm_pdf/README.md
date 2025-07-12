# Simple PDF LLM Example

This example shows how to read a PDF file, tokenize its text and perform a basic computation with a small language model.
The model is wrapped using PyTorch's **FSDP** (Fully Sharded Data Parallel).

## Requirements

Install the required Python packages. FSDP requires a PyTorch build with distributed support:

```bash
pip install PyPDF2 transformers torch
```

## Usage

Pass the path to a PDF when running the script. By default it uses the `distilgpt2` model from HuggingFace.

```bash
python main.py --pdf ../../openlog/\데이터로거(OPENLOG)_Rev1.1.pdf
```

You can specify the process group backend with `--backend` (defaults to `gloo`).

You can choose a different model with the `--model` option.

The script prints:

- Number of extracted characters from the PDF
- Token count from the tokenizer
- Model parameter count
- Output tensor shape from a single forward pass
