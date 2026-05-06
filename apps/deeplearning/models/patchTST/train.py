import argparse
import csv
import math
import random
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


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
    if len(values) < 3:
        raise ValueError("At least 3 numeric values are required.")
    return values


def normalize(values: list[float]) -> tuple[list[float], float, float]:
    min_value = min(values)
    max_value = max(values)
    span = max_value - min_value
    if math.isclose(span, 0.0):
        raise ValueError("All values are identical; normalization would divide by zero.")
    return [(value - min_value) / span for value in values], min_value, max_value


def make_windows(values: list[float], sequence_length: int) -> tuple[torch.Tensor, torch.Tensor]:
    if len(values) <= sequence_length:
        raise ValueError("The dataset must be longer than sequence_length.")

    xs = []
    ys = []
    for start in range(len(values) - sequence_length):
        end = start + sequence_length
        xs.append(values[start:end])
        ys.append(values[end])

    x_tensor = torch.tensor(xs, dtype=torch.float32).unsqueeze(-1)
    y_tensor = torch.tensor(ys, dtype=torch.float32).unsqueeze(-1)
    return x_tensor, y_tensor


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a small PatchTST next-step predictor.")
    parser.add_argument("--data", type=Path, default=BASE_DIR / "data/sample_sine.csv")
    parser.add_argument("--value-column", default="value")
    parser.add_argument("--sequence-length", type=int, default=24)
    parser.add_argument("--patch-length", type=int, default=6)
    parser.add_argument("--stride", type=int, default=3)
    parser.add_argument("--d-model", type=int, default=64)
    parser.add_argument("--nhead", type=int, default=4)
    parser.add_argument("--num-layers", type=int, default=2)
    parser.add_argument("--dim-feedforward", type=int, default=128)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=BASE_DIR / "checkpoints/patchtst_sample.pt")
    args = parser.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)

    values = load_series(args.data, args.value_column)
    normalized_values, min_value, max_value = normalize(values)
    x_tensor, y_tensor = make_windows(normalized_values, args.sequence_length)

    train_size = max(1, int(len(x_tensor) * 0.8))
    train_dataset = TensorDataset(x_tensor[:train_size], y_tensor[:train_size])
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)

    model = PatchTSTRegressor(
        sequence_length=args.sequence_length,
        patch_length=args.patch_length,
        stride=args.stride,
        d_model=args.d_model,
        nhead=args.nhead,
        num_layers=args.num_layers,
        dim_feedforward=args.dim_feedforward,
        dropout=args.dropout,
    )
    criterion = nn.MSELoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)

    for epoch in range(1, args.epochs + 1):
        model.train()
        epoch_loss = 0.0
        for batch_x, batch_y in train_loader:
            optimizer.zero_grad()
            prediction = model(batch_x)
            loss = criterion(prediction, batch_y)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * len(batch_x)

        if epoch == 1 or epoch % 50 == 0 or epoch == args.epochs:
            mean_loss = epoch_loss / len(train_dataset)
            print(f"epoch={epoch:04d} train_mse={mean_loss:.6f}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state": model.state_dict(),
            "sequence_length": args.sequence_length,
            "patch_length": args.patch_length,
            "stride": args.stride,
            "d_model": args.d_model,
            "nhead": args.nhead,
            "num_layers": args.num_layers,
            "dim_feedforward": args.dim_feedforward,
            "dropout": args.dropout,
            "value_column": args.value_column,
            "min_value": min_value,
            "max_value": max_value,
        },
        args.output,
    )
    print(f"saved checkpoint: {args.output}")


if __name__ == "__main__":
    main()
