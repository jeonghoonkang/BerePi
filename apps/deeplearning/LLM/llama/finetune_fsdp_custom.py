#!/usr/bin/env python3
"""Fine-tune a LLaMA model using FSDP with a custom text dataset.

This script loads plain text files using the HuggingFace `text` dataset loader
and fine-tunes a model using PyTorch's Fully Sharded Data Parallel (FSDP).
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
    parser = argparse.ArgumentParser(description="FSDP fine-tuning with custom text")
    parser.add_argument(
        "--model",
        default="meta-llama/Llama-2-7b-hf",
        help="Model checkpoint or HuggingFace repository",
    )
    parser.add_argument(
        "--data_files",
        required=True,
        help="Path to one or more text files for training (comma separated)",
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

    data_files = [p.strip() for p in args.data_files.split(",")]
    dataset = load_dataset("text", data_files=data_files, split="train")
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
