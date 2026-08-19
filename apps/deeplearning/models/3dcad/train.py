"""Train a B-rep geometry/topology classifier."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np
import torch
import yaml
from torch import nn
from torch.utils.data import DataLoader, Subset

from brep_learning.dataset import BrepDataset, collate_graphs
from brep_learning.model import BrepGraphNetwork


def move(batch, device):
    return {k: (v.to(device) if isinstance(v, torch.Tensor) else v) for k, v in batch.items()}


@torch.no_grad()
def evaluate(model, loader, device):
    model.eval(); correct = total = 0; loss_sum = 0.0
    loss_fn = nn.CrossEntropyLoss()
    for batch in loader:
        batch = move(batch, device)
        logits = model(batch["face_uv"], batch["face_attr"], batch["edge_index"], batch["edge_attr"], batch["batch"])
        loss_sum += loss_fn(logits, batch["label"]).item() * len(batch["label"])
        correct += (logits.argmax(1) == batch["label"]).sum().item(); total += len(batch["label"])
    return {"loss": loss_sum / max(total, 1), "accuracy": correct / max(total, 1)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.yaml"))
    args = parser.parse_args()
    with args.config.open(encoding="utf-8") as f: cfg = yaml.safe_load(f)
    base = args.config.resolve().parent
    resolve = lambda p: Path(p) if Path(p).is_absolute() else base / p
    seed = int(cfg["seed"]); random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    dataset = BrepDataset(resolve(cfg["data_dir"]), resolve(cfg["label_csv"]))
    indices = torch.randperm(len(dataset), generator=torch.Generator().manual_seed(seed)).tolist()
    cut = max(1, min(len(indices) - 1, round(len(indices) * float(cfg["train_ratio"]))))
    if len(indices) < 2: raise ValueError("At least two labeled CAD models are required")
    train_set, val_set = Subset(dataset, indices[:cut]), Subset(dataset, indices[cut:])
    loader_args = dict(batch_size=int(cfg["batch_size"]), num_workers=int(cfg["num_workers"]), collate_fn=collate_graphs)
    train_loader = DataLoader(train_set, shuffle=True, **loader_args)
    val_loader = DataLoader(val_set, shuffle=False, **loader_args)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model_args = {k: cfg[k] for k in ("num_classes", "hidden_dim", "message_passing_steps", "dropout")}
    model = BrepGraphNetwork(**model_args).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(cfg["learning_rate"]), weight_decay=float(cfg["weight_decay"]))
    loss_fn = nn.CrossEntropyLoss(); output = resolve(cfg["output_dir"]); output.mkdir(parents=True, exist_ok=True)
    best = -1.0; history = []
    for epoch in range(1, int(cfg["epochs"]) + 1):
        model.train(); train_loss = seen = 0
        for batch in train_loader:
            batch = move(batch, device); optimizer.zero_grad(set_to_none=True)
            logits = model(batch["face_uv"], batch["face_attr"], batch["edge_index"], batch["edge_attr"], batch["batch"])
            loss = loss_fn(logits, batch["label"]); loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0); optimizer.step()
            train_loss += loss.item() * len(batch["label"]); seen += len(batch["label"])
        metrics = evaluate(model, val_loader, device)
        row = {"epoch": epoch, "train_loss": train_loss / seen, **{f"val_{k}": v for k, v in metrics.items()}}
        history.append(row); print(json.dumps(row))
        if metrics["accuracy"] > best:
            best = metrics["accuracy"]
            torch.save({"model": model.state_dict(), "model_args": model_args, "config": cfg}, output / "best.pt")
    (output / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    print(f"best validation accuracy={best:.4f}; checkpoint={output / 'best.pt'}")


if __name__ == "__main__":
    main()
