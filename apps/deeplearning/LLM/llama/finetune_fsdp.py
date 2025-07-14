#!/usr/bin/env python3
"""Example of fine-tuning LLaMA with PyTorch FSDP on two GPUs.

This script uses HuggingFace Transformers and the wikitext-2 dataset to
illustrate how to enable FSDP training. It is intended for a workstation
with 2 RTX 4090 GPUs.

Run with:

    torchrun --nproc_per_node=2 finetune_fsdp.py --model meta-llama/Llama-2-7b-hf
"""

import argparse

from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
)



def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune LLaMA using FSDP")
    parser.add_argument(
        "--model",
        default="meta-llama/Llama-2-7b-hf",
        help="Model checkpoint or HuggingFace repository",
    )
    parser.add_argument(
        "--dataset",
        default="wikitext",
        help="HuggingFace dataset name",
    )
    parser.add_argument(
        "--subset",
        default="wikitext-2-raw-v1",
        help="Subset name for the dataset",
    )
    parser.add_argument(
        "--output_dir",
        default="./llama_fsdp_output",
        help="Directory for checkpoints",
    )
    parser.add_argument("--max_steps", type=int, default=10)
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=False)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype="auto"
    )

    dataset = load_dataset(args.dataset, args.subset, split="train[:1%]")
    dataset = dataset.map(
        lambda b: tokenizer(b["text"]),
        batched=True,
        remove_columns=["text"],
    )

    train_args = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        max_steps=args.max_steps,
        logging_steps=1,
        fsdp="full_shard auto_wrap",
        fsdp_transformer_layer_cls_to_wrap="LlamaDecoderLayer",
        save_total_limit=1,
        save_steps=5,
    )

    trainer = Trainer(model=model, args=train_args, train_dataset=dataset)
    trainer.train()


if __name__ == "__main__":
    main()
