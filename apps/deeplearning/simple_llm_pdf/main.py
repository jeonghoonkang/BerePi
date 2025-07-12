import argparse
import PyPDF2
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import torch.distributed as dist
from torch.distributed.fsdp import FullyShardedDataParallel as FSDP

def read_pdf(path: str) -> str:
    """Read text from a PDF file."""
    text = ""
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

def count_model_params(model) -> int:
    """Return the number of parameters in the model."""
    return sum(p.numel() for p in model.parameters())

def main():
    parser = argparse.ArgumentParser(description="PDF tokenization with LLM example")
    parser.add_argument("--pdf", required=True, help="Path to input PDF")
    parser.add_argument("--model", default="distilgpt2", help="HuggingFace model name")
    parser.add_argument("--backend", default="gloo", help="Distributed backend for FSDP")
    args = parser.parse_args()

    dist.init_process_group(backend=args.backend, rank=0, world_size=1)

    text = read_pdf(args.pdf)
    if not text:
        print("No text extracted from PDF")
        return

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    tokens = tokenizer(text, return_tensors="pt")
    print(f"Extracted {len(text)} characters")
    print(f"Token count: {tokens.input_ids.shape[1]}")

    model = AutoModelForCausalLM.from_pretrained(args.model)
    fsdp_model = FSDP(model)
    param_count = count_model_params(fsdp_model)
    print(f"Model '{args.model}' parameter count: {param_count:,}")

    with torch.no_grad():
        outputs = fsdp_model(**tokens)
    print(f"Output logits shape: {outputs.logits.shape}")

    dist.destroy_process_group()

if __name__ == "__main__":
    main()
