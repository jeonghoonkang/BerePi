"""Variable-sized B-rep graph dataset and mini-batch collation."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset


@dataclass
class BrepGraph:
    face_uv: torch.Tensor
    face_attr: torch.Tensor
    edge_index: torch.Tensor
    edge_attr: torch.Tensor
    label: torch.Tensor
    name: str


class BrepDataset(Dataset):
    """Loads preprocessed NPZ files using a `file,label` CSV manifest."""

    def __init__(self, data_dir: str | Path, label_csv: str | Path):
        self.data_dir = Path(data_dir)
        label_csv = Path(label_csv)
        with label_csv.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        if not rows or not {"file", "label"}.issubset(rows[0]):
            raise ValueError("labels CSV must contain headers: file,label")
        self.rows = [(row["file"], int(row["label"])) for row in rows]
        missing = [name for name, _ in self.rows if not (self.data_dir / Path(name).with_suffix(".npz")).is_file()]
        if missing:
            raise FileNotFoundError(f"Missing {len(missing)} preprocessed files; first: {missing[0]}")

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> BrepGraph:
        name, label = self.rows[index]
        path = self.data_dir / Path(name).with_suffix(".npz")
        with np.load(path, allow_pickle=False) as item:
            return BrepGraph(
                face_uv=torch.from_numpy(item["face_uv"]),
                face_attr=torch.from_numpy(item["face_attr"]),
                edge_index=torch.from_numpy(item["edge_index"]).long(),
                edge_attr=torch.from_numpy(item["edge_attr"]),
                label=torch.tensor(label, dtype=torch.long), name=name,
            )


def collate_graphs(items: list[BrepGraph]) -> dict[str, torch.Tensor | list[str]]:
    offsets, total = [], 0
    for item in items:
        offsets.append(total); total += item.face_uv.shape[0]
    edge_indices = [item.edge_index + offset for item, offset in zip(items, offsets)]
    batch = [torch.full((item.face_uv.shape[0],), i, dtype=torch.long) for i, item in enumerate(items)]
    return {
        "face_uv": torch.cat([x.face_uv for x in items]),
        "face_attr": torch.cat([x.face_attr for x in items]),
        "edge_index": torch.cat(edge_indices, dim=1),
        "edge_attr": torch.cat([x.edge_attr for x in items]),
        "batch": torch.cat(batch),
        "label": torch.stack([x.label for x in items]),
        "names": [x.name for x in items],
    }
