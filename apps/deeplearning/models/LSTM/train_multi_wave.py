import argparse
import csv
import math
import random
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


BASE_DIR = Path(__file__).resolve().parent


class MultiWaveLSTMRegressor(nn.Module):
    def __init__(self, input_size: int, hidden_size: int = 64, num_layers: int = 2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
        )
        self.fc = nn.Linear(hidden_size, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        output, _ = self.lstm(x)
        return self.fc(output[:, -1, :])


def parse_columns(raw_columns: str) -> list[str]:
    columns = [column.strip() for column in raw_columns.split(",") if column.strip()]
    if not columns:
        raise ValueError("At least one feature column is required.")
    return columns


def load_table(csv_path: Path, feature_columns: list[str], target_column: str) -> tuple[list[list[float]], list[float]]:
    with csv_path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        missing = [column for column in feature_columns + [target_column] if column not in fieldnames]
        if missing:
            raise ValueError(f"Missing columns in {csv_path}: {', '.join(missing)}")

        features = []
        targets = []
        for row in reader:
            try:
                feature_row = [float(row[column]) for column in feature_columns]
                target_value = float(row[target_column])
            except (TypeError, ValueError):
                continue
            features.append(feature_row)
            targets.append(target_value)

    if len(features) < 3:
        raise ValueError("At least 3 numeric rows are required.")
    return features, targets


def min_max(values: list[float]) -> tuple[float, float]:
    min_value = min(values)
    max_value = max(values)
    if math.isclose(max_value - min_value, 0.0):
        raise ValueError("All values are identical; normalization would divide by zero.")
    return min_value, max_value


def normalize_table(features: list[list[float]], targets: list[float]) -> tuple[list[list[float]], list[float], list[dict], dict]:
    feature_stats = []
    normalized_features = [[0.0 for _ in row] for row in features]

    for column_index in range(len(features[0])):
        column_values = [row[column_index] for row in features]
        min_value, max_value = min_max(column_values)
        feature_stats.append({"min": min_value, "max": max_value})
        span = max_value - min_value
        for row_index, row in enumerate(features):
            normalized_features[row_index][column_index] = (row[column_index] - min_value) / span

    target_min, target_max = min_max(targets)
    target_span = target_max - target_min
    normalized_targets = [(value - target_min) / target_span for value in targets]
    return normalized_features, normalized_targets, feature_stats, {"min": target_min, "max": target_max}


def make_windows(
    features: list[list[float]],
    targets: list[float],
    sequence_length: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    if len(features) <= sequence_length:
        raise ValueError("The dataset must be longer than sequence_length.")

    xs = []
    ys = []
    for start in range(len(features) - sequence_length):
        end = start + sequence_length
        xs.append(features[start:end])
        ys.append(targets[end])

    x_tensor = torch.tensor(xs, dtype=torch.float32)
    y_tensor = torch.tensor(ys, dtype=torch.float32).unsqueeze(-1)
    return x_tensor, y_tensor


def main() -> None:
    parser = argparse.ArgumentParser(description="Train an LSTM predictor with multiple wave inputs.")
    parser.add_argument("--data", type=Path, default=BASE_DIR / "data/sample_multi_wave.csv")
    parser.add_argument("--feature-columns", default="wave_1,wave_2,wave_3,wave_4,wave_5,wave_6")
    parser.add_argument("--target-column", default="target_mix")
    parser.add_argument("--sequence-length", type=int, default=16)
    parser.add_argument("--hidden-size", type=int, default=64)
    parser.add_argument("--num-layers", type=int, default=2)
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=0.005)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=BASE_DIR / "checkpoints/lstm_multi_wave.pt")
    args = parser.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)

    feature_columns = parse_columns(args.feature_columns)
    features, targets = load_table(args.data, feature_columns, args.target_column)
    normalized_features, normalized_targets, feature_stats, target_stats = normalize_table(features, targets)
    x_tensor, y_tensor = make_windows(normalized_features, normalized_targets, args.sequence_length)

    train_size = max(1, int(len(x_tensor) * 0.8))
    train_dataset = TensorDataset(x_tensor[:train_size], y_tensor[:train_size])
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)

    model = MultiWaveLSTMRegressor(
        input_size=len(feature_columns),
        hidden_size=args.hidden_size,
        num_layers=args.num_layers,
    )
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
            "feature_columns": feature_columns,
            "target_column": args.target_column,
            "feature_stats": feature_stats,
            "target_stats": target_stats,
            "sequence_length": args.sequence_length,
            "hidden_size": args.hidden_size,
            "num_layers": args.num_layers,
        },
        args.output,
    )
    print(f"saved checkpoint: {args.output}")


if __name__ == "__main__":
    main()
