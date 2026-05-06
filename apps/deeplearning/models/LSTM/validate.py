import argparse
import csv
import math
from pathlib import Path

import torch
from torch import nn
from PIL import Image, ImageDraw, ImageFont


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


def draw_prediction_plot(
    values: list[float],
    input_start: int,
    sequence_length: int,
    actual_value: float,
    predicted_value: float,
    output_path: Path,
) -> None:
    width = 1200
    height = 540
    left = 80
    top = 55
    right = 1165
    bottom = 470
    output_index = input_start + sequence_length

    min_y = min(min(values), actual_value, predicted_value)
    max_y = max(max(values), actual_value, predicted_value)
    y_padding = max((max_y - min_y) * 0.08, 0.1)
    min_y -= y_padding
    max_y += y_padding

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    def sx(index: int) -> float:
        return left + index / (len(values) - 1) * (right - left)

    def sy(value: float) -> float:
        return bottom - (value - min_y) / (max_y - min_y) * (bottom - top)

    title = "LSTM Validation Input and Output"
    draw.text(((width - draw.textlength(title, font=font)) / 2, 18), title, fill="#0f172a", font=font)
    draw.rectangle((left, top, right, bottom), outline="#cbd5e1", width=2)

    for ratio in [0.0, 0.25, 0.5, 0.75, 1.0]:
        value = min_y + ratio * (max_y - min_y)
        y = sy(value)
        draw.line((left, y, right, y), fill="#e2e8f0", width=1)
        draw.text((18, y - 6), f"{value:.2f}", fill="#475569", font=font)

    step = max(1, len(values) // 8)
    for index in range(0, len(values), step):
        x = sx(index)
        draw.line((x, top, x, bottom), fill="#f1f5f9", width=1)
        draw.text((x - 8, bottom + 12), str(index), fill="#475569", font=font)

    all_points = [(sx(index), sy(value)) for index, value in enumerate(values)]
    draw.line(all_points, fill="#94a3b8", width=2)

    input_end = input_start + sequence_length - 1
    draw.rectangle((sx(input_start), top, sx(input_end), bottom), fill="#dbeafe", outline="#60a5fa", width=2)
    input_points = [(sx(index), sy(values[index])) for index in range(input_start, input_end + 1)]
    draw.line(input_points, fill="#2563eb", width=5)
    for x, y in input_points:
        draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill="#1e3a8a")

    actual_x = sx(output_index)
    actual_y = sy(actual_value)
    predicted_y = sy(predicted_value)
    draw.line((actual_x, top, actual_x, bottom), fill="#fecaca", width=2)
    draw.ellipse((actual_x - 7, actual_y - 7, actual_x + 7, actual_y + 7), fill="#dc2626")
    draw.rectangle((actual_x - 7, predicted_y - 7, actual_x + 7, predicted_y + 7), fill="#16a34a")
    draw.line((actual_x, actual_y, actual_x, predicted_y), fill="#64748b", width=2)

    legend_x = right - 210
    legend_y = top + 16
    legend = [
        ("full sample", "#94a3b8"),
        ("input window", "#2563eb"),
        ("actual output", "#dc2626"),
        ("predicted output", "#16a34a"),
    ]
    for offset, (label, color) in enumerate(legend):
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
    parser = argparse.ArgumentParser(description="Validate a trained LSTM next-step predictor.")
    parser.add_argument("--data", type=Path, default=BASE_DIR / "data/sample_sine.csv")
    parser.add_argument("--checkpoint", type=Path, default=BASE_DIR / "checkpoints/lstm_sample.pt")
    parser.add_argument("--show", type=int, default=10)
    parser.add_argument("--plot-index", type=int, default=0)
    parser.add_argument("--plot-output", type=Path, default=BASE_DIR / "assets/lstm_validation_prediction.png")
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

    if not 0 <= args.plot_index < len(x_validation):
        raise ValueError(f"--plot-index must be between 0 and {len(x_validation) - 1}.")

    plot_start = validation_start + args.plot_index
    actual = denormalize(y_validation[args.plot_index].item(), min_value, max_value)
    predicted = denormalize(predictions[args.plot_index].item(), min_value, max_value)
    draw_prediction_plot(
        values=values,
        input_start=plot_start,
        sequence_length=sequence_length,
        actual_value=actual,
        predicted_value=predicted,
        output_path=args.plot_output,
    )
    print(f"saved validation plot: {args.plot_output}")


if __name__ == "__main__":
    main()
