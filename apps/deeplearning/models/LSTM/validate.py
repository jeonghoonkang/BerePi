import argparse
import csv
import math
from pathlib import Path

import torch
from torch import nn


BASE_DIR = Path(__file__).resolve().parent


class LSTMRegressor(nn.Module):
    def __init__(self, hidden_size: int = 32, num_layers: int = 1):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=1,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
        )
        self.fc = nn.Linear(hidden_size, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        output, _ = self.lstm(x)
        return self.fc(output[:, -1, :])


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
    parser = argparse.ArgumentParser(description="Validate a trained LSTM next-step predictor.")
    parser.add_argument("--data", type=Path, default=BASE_DIR / "data/sample_sine.csv")
    parser.add_argument("--checkpoint", type=Path, default=BASE_DIR / "checkpoints/lstm_sample.pt")
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

    model = LSTMRegressor(
        hidden_size=checkpoint["hidden_size"],
        num_layers=checkpoint["num_layers"],
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
