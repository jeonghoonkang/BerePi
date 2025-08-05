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
from rich.progress import Progress
from influxdb_client import InfluxDBClient, Point
from ultralytics import YOLO

MOTION_DIR = Path("/var/lib/motion")
OUTPUT_MOSAIC = Path("/tmp/motion_mosaic.jpg")
PEOPLE_GRAPH = Path("/tmp/person_count.png")
DISK_GRAPH = Path("/tmp/disk_free.png")

INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "token")
INFLUX_ORG = os.getenv("INFLUX_ORG", "org")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "bucket")


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


def create_mosaic(image_paths: Iterable[Path], output_path: Path) -> Path:
    imgs = [Image.open(p) for p in image_paths]
    w, h = imgs[0].size
    cols = ceil(sqrt(len(imgs)))
    rows = ceil(len(imgs) / cols)
    mosaic = Image.new("RGB", (cols * w, rows * h))

    with Progress() as progress:
        task = progress.add_task("Assembling mosaic", total=len(imgs))
        for idx, img in enumerate(imgs):
            x = (idx % cols) * w
            y = (idx // cols) * h
            mosaic.paste(img, (x, y))
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
            progress.advance(task)
    return counts


def write_counts(client: InfluxDBClient, counts: Dict[Path, int]) -> None:
    write_api = client.write_api()
    for path, num in counts.items():
        point = (
            Point("person_count")
            .tag("source", "motion")
            .field("count", num)
            .time(datetime.fromtimestamp(path.stat().st_mtime))
        )
        write_api.write(INFLUX_BUCKET, INFLUX_ORG, point)


def write_disk_free(client: InfluxDBClient) -> None:
    free = shutil.disk_usage("/").free
    point = Point("disk_free").field("bytes", free).time(datetime.utcnow())
    client.write_api().write(INFLUX_BUCKET, INFLUX_ORG, point)


def generate_graph(client: InfluxDBClient, measurement: str, output: Path) -> Path:
    query = f"from(bucket: '{INFLUX_BUCKET}') |> range(start: -48h) |> filter(fn: (r) => r['_measurement'] == '{measurement}')"
    tables = client.query_api().query(query, org=INFLUX_ORG)

    times: List[datetime] = []
    values: List[float] = []
    for table in tables:
        for record in table.records:
            times.append(record.get_time())
            values.append(record.get_value())

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

    model = YOLO("yolov8n.pt")

    people_counts = detect_people(model, images)

    with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
        write_counts(client, people_counts)
        write_disk_free(client)
        generate_graph(client, "person_count", PEOPLE_GRAPH)
        generate_graph(client, "disk_free", DISK_GRAPH)

    mosaic_path = create_mosaic(images, OUTPUT_MOSAIC)

    send_via_telegram([mosaic_path, PEOPLE_GRAPH, DISK_GRAPH])


if __name__ == "__main__":
    main()

