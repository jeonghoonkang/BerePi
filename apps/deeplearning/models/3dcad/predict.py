"""Extract one CAD model and classify it with a trained checkpoint."""

from __future__ import annotations

import argparse
from pathlib import Path

import torch

from brep_learning.extract import extract_brep
from brep_learning.model import BrepGraphNetwork


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cad_file", type=Path); parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--resolution", type=int, default=10)
    args = parser.parse_args(); device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = torch.load(args.checkpoint, map_location=device, weights_only=False)
    model = BrepGraphNetwork(**checkpoint["model_args"]).to(device)
    model.load_state_dict(checkpoint["model"]); model.eval()
    arrays = extract_brep(args.cad_file, args.resolution)
    tensors = {k: torch.from_numpy(arrays[k]).to(device) for k in ("face_uv", "face_attr", "edge_index", "edge_attr")}
    batch = torch.zeros(tensors["face_uv"].shape[0], dtype=torch.long, device=device)
    with torch.no_grad():
        probabilities = model(**tensors, batch=batch).softmax(1)[0].cpu()
    print({"class": int(probabilities.argmax()), "probabilities": probabilities.tolist()})


if __name__ == "__main__":
    main()
