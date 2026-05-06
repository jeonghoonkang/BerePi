import argparse
import csv
import math
from pathlib import Path

import torch
from torch import nn


BASE_DIR = Path(__file__).resolve().parent


class PatchTSTRegressor(nn.Module):
    def __init__(
        self,
        sequence_length: int,
        patch_length: int = 6,
        stride: int = 3,
        d_model: int = 64,
        nhead: int = 4,
        num_layers: int = 2,
        dim_feedforward: int = 128,
        dropout: float = 0.1,
    ):
        super().__init__()
        if patch_length > sequence_length:
            raise ValueError("patch_length must be smaller than or equal to sequence_length.")
        if d_model % nhead != 0:
            raise ValueError("d_model must be divisible by nhead.")

        self.patch_length = patch_length
        self.stride = stride
        self.num_patches = ((sequence_length - patch_length) // stride) + 1

        self.patch_projection = nn.Linear(patch_length, d_model)
        self.position_embedding = nn.Parameter(torch.zeros(1, self.num_patches, d_model))

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.norm = nn.LayerNorm(d_model)
        self.head = nn.Linear(self.num_patches * d_model, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        patches = x.squeeze(-1).unfold(dimension=1, size=self.patch_length, step=self.stride)
        tokens = self.patch_projection(patches) + self.position_embedding
        encoded = self.encoder(tokens)
        encoded = self.norm(encoded)
        return self.head(encoded.flatten(start_dim=1))


def load_series(csv_path: Path, value_column: str) -> list[float]:
    with csv_path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        if value_column not in (reader.fieldnames or []):
            raise ValueError(f"'{value_column}' column was not found in {csv_path}")
        values = []
        for row in reader:
            raw_value = row.get(value_column, "").strip()
            if not raw_value:
                continue
            values.append(float(raw_value))
    return values


def normalize(values: list[float], min_value: float, max_value: float) -> list[float]:
    span = max_value - min_value
    if math.isclose(span, 0.0):
        raise ValueError("Checkpoint min/max values are invalid.")
    return [(value - min_value) / span for value in values]


def denormalize(value: float, min_value: float, max_value: float) -> float:
    return value * (max_value - min_value) + min_value


def make_windows(values: list[float], sequence_length: int) -> tuple[torch.Tensor, torch.Tensor]:
    xs = []
    ys = []
    for start in range(len(values) - sequence_length):
        end = start + sequence_length
        xs.append(values[start:end])
        ys.append(values[end])
    return (
        torch.tensor(xs, dtype=torch.float32).unsqueeze(-1),
        torch.tensor(ys, dtype=torch.float32).unsqueeze(-1),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a trained PatchTST next-step predictor.")
    parser.add_argument("--data", type=Path, default=BASE_DIR / "data/sample_sine.csv")
    parser.add_argument("--checkpoint", type=Path, default=BASE_DIR / "checkpoints/patchtst_sample.pt")
    parser.add_argument("--show", type=int, default=10)
    args = parser.parse_args()

    checkpoint = torch.load(args.checkpoint, map_location="cpu")
    value_column = checkpoint["value_column"]
    sequence_length = checkpoint["sequence_length"]
    min_value = checkpoint["min_value"]
    max_value = checkpoint["max_value"]

    values = load_series(args.data, value_column)
    normalized_values = normalize(values, min_value, max_value)
    x_tensor, y_tensor = make_windows(normalized_values, sequence_length)

    validation_start = max(0, int(len(x_tensor) * 0.8))
    x_validation = x_tensor[validation_start:]
    y_validation = y_tensor[validation_start:]
    if len(x_validation) == 0:
        raise ValueError("No validation samples were created. Use more data or a shorter sequence length.")

    model = PatchTSTRegressor(
        sequence_length=sequence_length,
        patch_length=checkpoint["patch_length"],
        stride=checkpoint["stride"],
        d_model=checkpoint["d_model"],
        nhead=checkpoint["nhead"],
        num_layers=checkpoint["num_layers"],
        dim_feedforward=checkpoint["dim_feedforward"],
        dropout=checkpoint["dropout"],
    )
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    with torch.no_grad():
        predictions = model(x_validation)

    errors = predictions - y_validation
    mse = torch.mean(errors.pow(2)).item()
    mae = torch.mean(errors.abs()).item()
    rmse = math.sqrt(mse)

    print(f"validation_samples={len(x_validation)}")
    print(f"mse={mse:.6f} rmse={rmse:.6f} mae={mae:.6f}")
    print("index,actual,predicted")
    for index in range(min(args.show, len(x_validation))):
        actual = denormalize(y_validation[index].item(), min_value, max_value)
        predicted = denormalize(predictions[index].item(), min_value, max_value)
        print(f"{index},{actual:.4f},{predicted:.4f}")


if __name__ == "__main__":
    main()
