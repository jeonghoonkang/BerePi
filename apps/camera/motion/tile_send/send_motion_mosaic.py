#!/usr/bin/env python3
"""Monitor motion images, detect people, create mosaics and send via telegram.

The script waits for five new images to appear in ``/var/lib/motion``. Once the
threshold is met, it collects the next eighteen images, runs a person detection
model on them and stores the counts to InfluxDB. A mosaic of the images is
generated along with two graphs for the last 48 hours: number of detected
people and remaining HDD space. All artefacts are then sent using
``telegram-send``. Progress for long running operations is displayed with
``rich``.
"""

from __future__ import annotations

import os
import subprocess
import time
import shutil
from datetime import datetime
from math import ceil, sqrt
from pathlib import Path
from typing import Dict, Iterable, List

import matplotlib.pyplot as plt
from PIL import Image
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
INFLUX_USER = os.getenv("INFLUX_USER", "")
INFLUX_PASSWORD = os.getenv("INFLUX_PASSWORD", "")
INFLUX_DB = os.getenv("INFLUX_DB", "")

console = Console()


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



def _images_since(start: datetime) -> List[Path]:
    """Return images created after ``start``."""
    images: List[Path] = []
    for ext in ("*.jpg", "*.jpeg", "*.png"):
        images.extend(p for p in MOTION_DIR.glob(ext) if datetime.fromtimestamp(p.stat().st_mtime) >= start)
    return sorted(images, key=lambda p: p.stat().st_mtime)


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


def create_mosaic(image_paths: Iterable[Path], output_path: Path) -> Path:
    paths = list(image_paths)
    imgs = [Image.open(p) for p in paths]

    w, h = imgs[0].size
    cols = ceil(sqrt(len(imgs)))
    rows = ceil(len(imgs) / cols)
    mosaic = Image.new("RGB", (cols * w, rows * h))

    with Progress() as progress:
        task = progress.add_task("Assembling mosaic", total=len(imgs))
        for idx, (img, path) in enumerate(zip(imgs, paths)):
            x = (idx % cols) * w
            y = (idx // cols) * h
            mosaic.paste(img, (x, y))
            progress.print(str(path))

            progress.advance(task)
    mosaic.save(output_path)
    return output_path


def detect_people(model: YOLO, image_paths: Iterable[Path]) -> Dict[Path, int]:
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
    return counts


def write_counts(client: InfluxDBClient, counts: Dict[Path, int]) -> None:
    points = []
    for path, num in counts.items():
        points.append(
            {
                "measurement": "person_count",
                "tags": {"source": "motion"},
                "time": datetime.utcfromtimestamp(path.stat().st_mtime).isoformat() + "Z",
                "fields": {"count": num},
            }
        )
    if points:
        client.write_points(points)


def write_disk_free(client: InfluxDBClient) -> None:
    free = shutil.disk_usage("/").free
    point = {
        "measurement": "disk_free",
        "time": datetime.utcnow().isoformat() + "Z",
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
        plt.plot(times, values)
        plt.title(measurement)
        plt.xlabel("time")
        plt.ylabel("value")
        plt.tight_layout()
        plt.savefig(output)
        plt.close()
    return output


def send_via_telegram(paths: Iterable[Path]) -> None:
    cmd = ["telegram-send"]
    for path in paths:
        cmd.extend(["--image", str(path)])
    subprocess.run(cmd, check=True)


def main() -> None:
    start_time = datetime.now()
    wait_for_images(start_time, 5)  # wait until 5 images appear
    trigger = datetime.now()
    images = wait_for_images(trigger, 18)

    log_images(images)


    model = YOLO("yolov8n.pt")

    people_counts = detect_people(model, images)

    ensure_influx_running()

    client = InfluxDBClient(
        host=INFLUX_HOST,
        port=INFLUX_PORT,
        username=INFLUX_USER or None,
        password=INFLUX_PASSWORD or None,
        database=INFLUX_DB,
    )
    write_counts(client, people_counts)
    write_disk_free(client)
    generate_graph(client, "person_count", "count", PEOPLE_GRAPH)
    generate_graph(client, "disk_free", "bytes", DISK_GRAPH)
    client.close()

    mosaic_path = create_mosaic(images, OUTPUT_MOSAIC)

    send_via_telegram([mosaic_path, PEOPLE_GRAPH, DISK_GRAPH])


if __name__ == "__main__":
    main()

