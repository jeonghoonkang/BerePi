import argparse
import csv
import math
from pathlib import Path

import torch
from torch import nn
from PIL import Image, ImageDraw, ImageFont


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
    return features, targets


def normalize_table(features: list[list[float]], targets: list[float], feature_stats: list[dict], target_stats: dict) -> tuple[list[list[float]], list[float]]:
    normalized_features = [[0.0 for _ in row] for row in features]
    for column_index, stats in enumerate(feature_stats):
        span = stats["max"] - stats["min"]
        if math.isclose(span, 0.0):
            raise ValueError("Feature min/max values are invalid.")
        for row_index, row in enumerate(features):
            normalized_features[row_index][column_index] = (row[column_index] - stats["min"]) / span

    target_span = target_stats["max"] - target_stats["min"]
    if math.isclose(target_span, 0.0):
        raise ValueError("Target min/max values are invalid.")
    normalized_targets = [(value - target_stats["min"]) / target_span for value in targets]
    return normalized_features, normalized_targets


def denormalize(value: float, stats: dict) -> float:
    return value * (stats["max"] - stats["min"]) + stats["min"]


def make_windows(
    features: list[list[float]],
    targets: list[float],
    sequence_length: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    xs = []
    ys = []
    for start in range(len(features) - sequence_length):
        end = start + sequence_length
        xs.append(features[start:end])
        ys.append(targets[end])
    return (
        torch.tensor(xs, dtype=torch.float32),
        torch.tensor(ys, dtype=torch.float32).unsqueeze(-1),
    )


def draw_prediction_plot(
    features: list[list[float]],
    targets: list[float],
    feature_columns: list[str],
    target_column: str,
    input_start: int,
    sequence_length: int,
    actual_value: float,
    predicted_value: float,
    output_path: Path,
) -> None:
    width = 1200
    height = 640
    left = 80
    top = 55
    right = 1165
    bottom = 550
    output_index = input_start + sequence_length

    all_values = [value for row in features for value in row] + targets + [actual_value, predicted_value]
    min_y = min(all_values)
    max_y = max(all_values)
    y_padding = max((max_y - min_y) * 0.08, 0.1)
    min_y -= y_padding
    max_y += y_padding

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    def sx(index: int) -> float:
        return left + index / (len(targets) - 1) * (right - left)

    def sy(value: float) -> float:
        return bottom - (value - min_y) / (max_y - min_y) * (bottom - top)

    title = "Multi-Wave LSTM Validation Input and Output"
    draw.text(((width - draw.textlength(title, font=font)) / 2, 18), title, fill="#0f172a", font=font)
    draw.rectangle((left, top, right, bottom), outline="#cbd5e1", width=2)

    for ratio in [0.0, 0.25, 0.5, 0.75, 1.0]:
        value = min_y + ratio * (max_y - min_y)
        y = sy(value)
        draw.line((left, y, right, y), fill="#e2e8f0", width=1)
        draw.text((18, y - 6), f"{value:.2f}", fill="#475569", font=font)

    step = max(1, len(targets) // 8)
    for index in range(0, len(targets), step):
        x = sx(index)
        draw.line((x, top, x, bottom), fill="#f1f5f9", width=1)
        draw.text((x - 8, bottom + 12), str(index), fill="#475569", font=font)

    colors = ["#2563eb", "#7c3aed", "#0891b2", "#f97316", "#84cc16", "#db2777"]
    for column_index, column_name in enumerate(feature_columns):
        color = colors[column_index % len(colors)]
        points = [(sx(index), sy(row[column_index])) for index, row in enumerate(features)]
        draw.line(points, fill=color, width=2)

    target_points = [(sx(index), sy(value)) for index, value in enumerate(targets)]
    draw.line(target_points, fill="#111827", width=4)

    input_end = input_start + sequence_length - 1
    draw.rectangle((sx(input_start), top, sx(input_end), bottom), fill="#dbeafe", outline="#60a5fa", width=2)
    for column_index in range(len(feature_columns)):
        color = colors[column_index % len(colors)]
        input_points = [(sx(index), sy(features[index][column_index])) for index in range(input_start, input_end + 1)]
        draw.line(input_points, fill=color, width=4)
        for x, y in input_points:
            draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=color)

    actual_x = sx(output_index)
    actual_y = sy(actual_value)
    predicted_y = sy(predicted_value)
    draw.line((actual_x, top, actual_x, bottom), fill="#fecaca", width=2)
    draw.ellipse((actual_x - 7, actual_y - 7, actual_x + 7, actual_y + 7), fill="#dc2626")
    draw.rectangle((actual_x - 7, predicted_y - 7, actual_x + 7, predicted_y + 7), fill="#16a34a")
    draw.line((actual_x, actual_y, actual_x, predicted_y), fill="#64748b", width=2)

    legend_x = right - 190
    legend_y = top + 14
    legend_items = [(name, colors[index % len(colors)]) for index, name in enumerate(feature_columns)]
    legend_items += [(target_column, "#111827"), ("actual output", "#dc2626"), ("predicted output", "#16a34a")]
    for offset, (label, color) in enumerate(legend_items):
        y = legend_y + offset * 18
        draw.rectangle((legend_x, y + 3, legend_x + 12, y + 12), fill=color)
        draw.text((legend_x + 18, y), label, fill="#334155", font=font)

    draw.text(((width - draw.textlength("step", font=font)) / 2, height - 32), "step", fill="#334155", font=font)
    draw.text((16, top - 24), "value", fill="#334155", font=font)
    draw.text((sx(input_start), bottom + 30), "input start", fill="#2563eb", font=font)
    draw.text((actual_x - 24, bottom + 30), "output", fill="#dc2626", font=font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate an LSTM predictor with multiple wave inputs.")
    parser.add_argument("--data", type=Path, default=BASE_DIR / "data/sample_multi_wave.csv")
    parser.add_argument("--checkpoint", type=Path, default=BASE_DIR / "checkpoints/lstm_multi_wave.pt")
    parser.add_argument("--show", type=int, default=10)
    parser.add_argument("--plot-index", type=int, default=0)
    parser.add_argument("--plot-output", type=Path, default=BASE_DIR / "assets/lstm_multi_wave_validation_prediction.png")
    args = parser.parse_args()

    checkpoint = torch.load(args.checkpoint, map_location="cpu")
    feature_columns = checkpoint["feature_columns"]
    target_column = checkpoint["target_column"]
    sequence_length = checkpoint["sequence_length"]
    target_stats = checkpoint["target_stats"]

    features, targets = load_table(args.data, feature_columns, target_column)
    normalized_features, normalized_targets = normalize_table(
        features,
        targets,
        checkpoint["feature_stats"],
        target_stats,
    )
    x_tensor, y_tensor = make_windows(normalized_features, normalized_targets, sequence_length)

    validation_start = max(0, int(len(x_tensor) * 0.8))
    x_validation = x_tensor[validation_start:]
    y_validation = y_tensor[validation_start:]
    if len(x_validation) == 0:
        raise ValueError("No validation samples were created. Use more data or a shorter sequence length.")

    model = MultiWaveLSTMRegressor(
        input_size=len(feature_columns),
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

    print(f"feature_columns={','.join(feature_columns)}")
    print(f"target_column={target_column}")
    print(f"validation_samples={len(x_validation)}")
    print(f"mse={mse:.6f} rmse={rmse:.6f} mae={mae:.6f}")
    print("index,actual,predicted")
    for index in range(min(args.show, len(x_validation))):
        actual = denormalize(y_validation[index].item(), target_stats)
        predicted = denormalize(predictions[index].item(), target_stats)
        print(f"{index},{actual:.5f},{predicted:.5f}")

    if not 0 <= args.plot_index < len(x_validation):
        raise ValueError(f"--plot-index must be between 0 and {len(x_validation) - 1}.")

    plot_start = validation_start + args.plot_index
    actual = denormalize(y_validation[args.plot_index].item(), target_stats)
    predicted = denormalize(predictions[args.plot_index].item(), target_stats)
    draw_prediction_plot(
        features=features,
        targets=targets,
        feature_columns=feature_columns,
        target_column=target_column,
        input_start=plot_start,
        sequence_length=sequence_length,
        actual_value=actual,
        predicted_value=predicted,
        output_path=args.plot_output,
    )
    print(f"saved validation plot: {args.plot_output}")


if __name__ == "__main__":
    main()
