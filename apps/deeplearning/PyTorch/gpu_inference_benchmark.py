import argparse
import time
from typing import Tuple

import torch


class SimpleCNN(torch.nn.Module):
    """A small convolutional network for benchmarking purposes."""

    def __init__(self) -> None:
        super().__init__()
        self.conv1 = torch.nn.Conv2d(3, 16, 3, stride=1, padding=1)
        self.pool = torch.nn.MaxPool2d(2, 2)
        self.fc1 = torch.nn.Linear(16 * 16 * 16, 10)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.pool(torch.nn.functional.relu(self.conv1(x)))
        x = x.flatten(1)
        return self.fc1(x)


def select_device() -> torch.device:
    """Return a CUDA device if available, otherwise CPU."""

    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def synchronize_if_cuda(device: torch.device) -> None:
    """Synchronize CUDA device if applicable to ensure accurate timing."""

    if device.type == "cuda":
        torch.cuda.synchronize()


def prepare_inputs(batch_size: int, device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    """Create random inputs for benchmarking."""

    return torch.randn(batch_size, 3, 32, 32, device=device, dtype=dtype)


def benchmark(
    model: torch.nn.Module,
    batch_size: int,
    warmup_iters: int,
    benchmark_iters: int,
    use_half: bool,
) -> Tuple[float, float]:
    """Run a simple throughput/latency benchmark.

    Returns a tuple containing the average latency (seconds) and throughput (samples/second).
    """

    device = select_device()
    model = model.eval().to(device)

    dtype = torch.float16 if use_half and device.type == "cuda" else torch.float32
    inputs = prepare_inputs(batch_size, device, dtype)

    if device.type == "cuda":
        torch.backends.cudnn.benchmark = True

    with torch.no_grad():
        for _ in range(warmup_iters):
            model(inputs)
        synchronize_if_cuda(device)

        start = time.perf_counter()
        for _ in range(benchmark_iters):
            model(inputs)
        synchronize_if_cuda(device)

    elapsed = time.perf_counter() - start
    avg_latency = elapsed / benchmark_iters
    throughput = batch_size / avg_latency

    return avg_latency, throughput


def print_results(
    device: torch.device,
    batch_size: int,
    dtype: torch.dtype,
    warmup_iters: int,
    benchmark_iters: int,
    avg_latency: float,
    throughput: float,
) -> None:
    """Display benchmark results in a user-friendly format."""

    print(f"Device          : {device}")
    print(f"Batch size      : {batch_size}")
    print(f"Data type       : {dtype}")
    print(f"Warm-up iters   : {warmup_iters}")
    print(f"Benchmark iters : {benchmark_iters}")
    print(f"Avg latency     : {avg_latency * 1000:.3f} ms")
    print(f"Throughput      : {throughput:.2f} samples/sec")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PyTorch GPU inference benchmark")
    parser.add_argument("--batch-size", type=int, default=32, help="number of samples per batch")
    parser.add_argument("--warmup-iters", type=int, default=20, help="iterations discarded for warm-up")
    parser.add_argument("--benchmark-iters", type=int, default=100, help="iterations measured for timing")
    parser.add_argument(
        "--half",
        action="store_true",
        help="use float16 when running on GPU for faster throughput",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    device = select_device()
    model = SimpleCNN()

    avg_latency, throughput = benchmark(
        model=model,
        batch_size=args.batch_size,
        warmup_iters=args.warmup_iters,
        benchmark_iters=args.benchmark_iters,
        use_half=args.half,
    )

    dtype = torch.float16 if args.half and device.type == "cuda" else torch.float32
    print_results(
        device=device,
        batch_size=args.batch_size,
        dtype=dtype,
        warmup_iters=args.warmup_iters,
        benchmark_iters=args.benchmark_iters,
        avg_latency=avg_latency,
        throughput=throughput,
    )


if __name__ == "__main__":
    main()
