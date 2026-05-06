import argparse
import csv
import math
import random
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


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
    parser = argparse.ArgumentParser(description="Train a small LSTM next-step predictor.")
    parser.add_argument("--data", type=Path, default=BASE_DIR / "data/sample_sine.csv")
    parser.add_argument("--value-column", default="value")
    parser.add_argument("--sequence-length", type=int, default=10)
    parser.add_argument("--hidden-size", type=int, default=32)
    parser.add_argument("--num-layers", type=int, default=1)
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=BASE_DIR / "checkpoints/lstm_sample.pt")
    args = parser.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)

    values = load_series(args.data, args.value_column)
    normalized_values, min_value, max_value = normalize(values)
    x_tensor, y_tensor = make_windows(normalized_values, args.sequence_length)

    train_size = max(1, int(len(x_tensor) * 0.8))
    train_dataset = TensorDataset(x_tensor[:train_size], y_tensor[:train_size])
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)

    model = LSTMRegressor(hidden_size=args.hidden_size, num_layers=args.num_layers)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate)

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
            "hidden_size": args.hidden_size,
            "num_layers": args.num_layers,
            "sequence_length": args.sequence_length,
            "value_column": args.value_column,
            "min_value": min_value,
            "max_value": max_value,
        },
        args.output,
    )
    print(f"saved checkpoint: {args.output}")


if __name__ == "__main__":
    main()
