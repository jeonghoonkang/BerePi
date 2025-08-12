#!/usr/bin/env python3
"""Monitor motion images, detect people, create mosaics and send via telegram.

The script waits for five new images to appear in ``/var/lib/motion``. Once the
threshold is met, it collects the next sixteen images, runs a person detection
model on them and stores the counts to InfluxDB. A mosaic of the images is
generated along with two graphs for the last 48 hours: number of detected
people and remaining HDD space. All artefacts are then sent using
``telegram-send``. Progress for long running operations is displayed with
``rich``.

When ``--date YYYY-MM-DD`` is supplied, the script instead processes all images
from that day, sending mosaics of the photos in 4x4 batches.
"""

from __future__ import annotations

import os
import subprocess
import time
import shutil
import argparse
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

from pathlib import Path
from typing import Dict, Iterable, List

try:
    import psutil
except ImportError:  # pragma: no cover - optional dependency
    psutil = None

import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont
from rich.console import Console
from rich.progress import Progress
# use the classic influxdb client instead of raw HTTP requests
from influxdb import InfluxDBClient

from ultralytics import YOLO

MOTION_DIR = Path("/var/lib/motion")
OUTPUT_MOSAIC = Path("/tmp/motion_mosaic.jpg")
PEOPLE_GRAPH = Path("/tmp/person_count.png")
DISK_GRAPH = Path("/tmp/disk_free.png")

INFLUX_HOST = os.getenv("INFLUX_HOST", "localhost")
INFLUX_PORT = int(os.getenv("INFLUX_PORT", "8086"))
INFLUX_USER = os.getenv("INFLUX_USER", "admin")
INFLUX_PASSWORD = os.getenv("INFLUX_PASSWORD", "admin")
INFLUX_DB = os.getenv("INFLUX_DB", "motion")

KST = ZoneInfo("Asia/Seoul")

console = Console()


def print_system_usage(tag: str = "", disk_path: str = str(MOTION_DIR)) -> None:
    """Print current system CPU, RAM and disk usage with an optional tag."""
    if psutil is None:
        console.print(f"{tag}CPU/RAM/Disk usage unavailable (psutil missing)")
        return
    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    usage = psutil.disk_usage(disk_path)
    free_gb = usage.free / (1024 ** 3)
    console.print(
        f"{tag}CPU: {cpu:.1f}% | RAM: {mem.percent:.1f}% | Disk Free: {free_gb:.1f} GB"
    )


def ensure_influx_running() -> None:
    """Start the InfluxDB service if it is not running."""
    running = subprocess.run(
        ["pgrep", "-f", "influxd"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode
    if running != 0:
        console.print("InfluxDB not running, attempting to start...")
        started = subprocess.run(
            ["systemctl", "start", "influxdb"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        if started != 0:
            subprocess.Popen(
                ["influxd"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        time.sleep(5)


def ensure_database(client: InfluxDBClient, name: str) -> None:
    """Create the given database in InfluxDB if it doesn't exist."""
    try:
        existing = {db["name"] for db in client.get_list_database()}
        if name not in existing:
            client.create_database(name)
    except Exception as exc:  # pragma: no cover - best effort
        console.print(f"Failed to verify/create database {name}: {exc}")



def _images_in_range(start: datetime, end: datetime) -> List[Path]:
    """Return image paths whose mtime lies between ``start`` and ``end``."""
    images: List[Path] = []

    exts = {".jpg", ".jpeg", ".png"}
    for entry in os.scandir(MOTION_DIR):
        if not entry.is_file():
            continue
        if not entry.name.lower().endswith(tuple(exts)):
            continue
        mtime = datetime.fromtimestamp(entry.stat().st_mtime)
        if start <= mtime <= end:
            images.append(Path(entry.path))
    return sorted(images, key=lambda p: p.stat().st_mtime, reverse=True)


def _images_since(start: datetime) -> List[Path]:
    """Return images newer than ``start`` limited to the last four days."""
    now = datetime.now()
    cutoff = max(start, now - timedelta(days=2))
    return _images_in_range(cutoff, now)


def images_for_day(day: date) -> List[Path]:
    """Return all images for the given ``day`` (00:00-23:59)."""
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)
    return _images_in_range(start, end)


def wait_for_images(start: datetime, count: int) -> List[Path]:
    """Block until ``count`` images exist after ``start``."""
    while True:
        imgs = _images_since(start)
        if len(imgs) >= count:
            return imgs[:count]
        time.sleep(2)


def log_images(image_paths: Iterable[Path]) -> None:
    """Print paths of images being processed with progress."""
    paths = list(image_paths)
    with Progress() as progress:
        task = progress.add_task("Images", total=len(paths))
        for p in paths:
            progress.print(str(p))
            progress.advance(task)


def create_mosaic(
    image_paths: Iterable[Path], output_path: Path, cols: int = 4, rows: int = 4
) -> Path:
    """Assemble images into a mosaic of ``cols`` by ``rows`` tiles.

    The earliest timestamp among the images is rendered onto the mosaic.
    """

    paths = list(image_paths)[: cols * rows]
    if not paths:
        raise ValueError("No images provided for mosaic")
    imgs = [Image.open(p) for p in paths]

    w, h = imgs[0].size
    mosaic = Image.new("RGB", (cols * w, rows * h))

    with Progress() as progress:
        task = progress.add_task("Assembling mosaic", total=len(imgs))
        for idx, (img, path) in enumerate(zip(imgs, paths)):
            x = (idx % cols) * w
            y = (idx // cols) * h
            mosaic.paste(img, (x, y))
            progress.print(str(path))

            progress.advance(task)

    # annotate with the earliest timestamp of the included images
    earliest = min(paths, key=lambda p: p.stat().st_mtime).stat().st_mtime
    time_text = datetime.fromtimestamp(earliest, KST).strftime("%Y-%m-%d %H:%M:%S")
    draw = ImageDraw.Draw(mosaic)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24
        )
    except OSError:  # pragma: no cover - font may be missing
        font = ImageFont.load_default()

    _, _, _, text_height = draw.textbbox((0, 0), time_text, font=font)
    x, y = 10, mosaic.height - text_height - 10
    # draw black outline for readability
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx or dy:
                draw.text((x + dx, y + dy), time_text, font=font, fill="black")
    draw.text((x, y), time_text, font=font, fill="white")

    mosaic.save(output_path)
    return output_path


def detect_people(
    model: YOLO, image_paths: Iterable[Path], client: InfluxDBClient | None = None
) -> Dict[Path, int]:
    """Detect people in images and optionally write counts to InfluxDB."""

    paths = list(image_paths)
    counts: Dict[Path, int] = {}
    with Progress() as progress:
        task = progress.add_task("Detecting people", total=len(paths))
        for path in paths:
            results = model(str(path))
            persons = sum(1 for c in results[0].boxes.cls if int(c) == 0)
            counts[path] = persons
            progress.print(str(path))
            progress.advance(task)

    if client is not None:
        write_counts(client, counts)

    return counts


def write_counts(client: InfluxDBClient, counts: Dict[Path, int]) -> None:
    points = []
    for path, num in counts.items():
        points.append(
            {
                "measurement": "person_count",
                "tags": {"source": "motion"},
                "time": datetime.fromtimestamp(path.stat().st_mtime, KST).isoformat(),
                "fields": {"count": num},
            }
        )
    if points:
        client.write_points(points)


def write_disk_free(client: InfluxDBClient) -> None:
    free = shutil.disk_usage("/").free
    point = {
        "measurement": "disk_free",
        "time": datetime.now(KST).isoformat(),
        "fields": {"bytes": free},
    }
    client.write_points([point])


def generate_graph(
    client: InfluxDBClient, measurement: str, field: str, output: Path
) -> Path:
    query = (
        f'SELECT "{field}" FROM "{measurement}" '
        f'WHERE time > now() - 48h'
    )
    result = client.query(query)
    points = list(result.get_points(measurement=measurement))

    times: List[datetime] = []
    values: List[float] = []
    for p in points:
        times.append(datetime.fromisoformat(p["time"].replace("Z", "+00:00")))
        values.append(p[field])


    if times and values:
        plt.figure()
        plt.plot(times, values, "o", linestyle="none")
        plt.title(measurement)
        plt.xlabel("time")
        plt.ylabel("value")
        plt.grid(True, linestyle="--", linewidth=0.5)

        plt.tight_layout()
        plt.savefig(output)
        plt.close()
    return output


def send_via_telegram(paths: Iterable[Path], delay: float = 1.0) -> None:
    for path in paths:
        subprocess.run(["telegram-send", "-i", str(path)], check=True)
        time.sleep(delay)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD to mosaic instead of live feed")
    args = parser.parse_args()

    perf_start = time.perf_counter()
    print_system_usage("Start ")

    if args.date:
        target_day = datetime.strptime(args.date, "%Y-%m-%d").date()
        images = images_for_day(target_day)
        if not images:
            console.print(f"No images found for {args.date}")
            print_system_usage("End ")
            console.print(f"Elapsed time: {time.perf_counter() - perf_start:.2f}s")
            return

        model = YOLO("yolov8n.pt")
        ensure_influx_running()
        client = InfluxDBClient(
            host=INFLUX_HOST,
            port=INFLUX_PORT,
            username=INFLUX_USER or None,
            password=INFLUX_PASSWORD or None,
        )
        ensure_database(client, INFLUX_DB)
        client.switch_database(INFLUX_DB)

        for idx in range(0, len(images), 16):
            batch = images[idx : idx + 16]
            log_images(batch)
            detect_people(model, batch, client)
            mosaic_path = OUTPUT_MOSAIC.with_name(f"motion_mosaic_{idx//16}.jpg")
            create_mosaic(batch, mosaic_path)
            send_via_telegram([mosaic_path])

        write_disk_free(client)
        generate_graph(client, "person_count", "count", PEOPLE_GRAPH)
        generate_graph(client, "disk_free", "bytes", DISK_GRAPH)
        send_via_telegram([PEOPLE_GRAPH, DISK_GRAPH])
        client.close()

        print_system_usage("End ")
        console.print(f"Elapsed time: {time.perf_counter() - perf_start:.2f}s")
        return

    start_time = datetime.now()
    wait_for_images(start_time, 5)  # wait until 5 images appear
    trigger = datetime.now()
    images = wait_for_images(trigger, 16)

    log_images(images)

    model = YOLO("yolov8n.pt")

    ensure_influx_running()
    client = InfluxDBClient(
        host=INFLUX_HOST,
        port=INFLUX_PORT,
        username=INFLUX_USER or None,
        password=INFLUX_PASSWORD or None,
    )
    ensure_database(client, INFLUX_DB)
    client.switch_database(INFLUX_DB)

    detect_people(model, images, client)
    write_disk_free(client)
    generate_graph(client, "person_count", "count", PEOPLE_GRAPH)
    generate_graph(client, "disk_free", "bytes", DISK_GRAPH)
    client.close()

    mosaic_path = create_mosaic(images, OUTPUT_MOSAIC)

    send_via_telegram([mosaic_path, PEOPLE_GRAPH, DISK_GRAPH])

    print_system_usage("End ")
    console.print(f"Elapsed time: {time.perf_counter() - perf_start:.2f}s")


if __name__ == "__main__":
    main()

