#!/usr/bin/env python3
"""Minimal FSDP fine-tuning example using plain text files."""

import argparse
import os
from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForCausalLM, default_data_collator
import torch
import torch.distributed as dist
from torch.distributed.fsdp import FullyShardedDataParallel as FSDP
from torch.utils.data import DataLoader


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual FSDP fine-tuning example")
    parser.add_argument("--model", default="meta-llama/Llama-2-7b-hf")
    parser.add_argument("--data_files", required=True,
                        help="Comma separated list of text files")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch_size", type=int, default=1)
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--output_dir", default="./llama_fsdp_output")
    args = parser.parse_args()

    dist.init_process_group("nccl")
    rank = dist.get_rank()
    device = torch.device(f"cuda:{rank}")

    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=False)
    model = AutoModelForCausalLM.from_pretrained(args.model, torch_dtype=torch.float16)
    fsdp_model = FSDP(model.to(device))

    files = [p.strip() for p in args.data_files.split(",")]
    dataset = load_dataset("text", data_files=files, split="train")
    tokenized = dataset.map(lambda b: tokenizer(b["text"]), batched=True, remove_columns=["text"])
    dataloader = DataLoader(tokenized, batch_size=args.batch_size, shuffle=True,
                            collate_fn=default_data_collator)

    optim = torch.optim.AdamW(fsdp_model.parameters(), lr=args.lr)

    fsdp_model.train()
    for _ in range(args.epochs):
        for batch in dataloader:
            batch = {k: v.to(device) for k, v in batch.items()}
            outputs = fsdp_model(**batch, labels=batch["input_ids"])
            loss = outputs.loss
            loss.backward()
            optim.step()
            optim.zero_grad()
        if rank == 0:
            print(f"Epoch done, loss: {loss.item():.4f}")

    if rank == 0:
        os.makedirs(args.output_dir, exist_ok=True)
        fsdp_model.cpu()
        fsdp_model.save_pretrained(args.output_dir)

    dist.destroy_process_group()


if __name__ == "__main__":
    main()
