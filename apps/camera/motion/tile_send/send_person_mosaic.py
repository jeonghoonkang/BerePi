#!/usr/bin/env python3
"""Detect people in recent motion images and report to InfluxDB.

The script scans ``/var/lib/motion`` for JPG images created within the last
30 minutes. Each image is analysed with a YOLO model and the number of detected
persons is written to InfluxDB using the timestamp encoded in the file name. A
count of zero is recorded when no person is found. If no new images are
available the script exits quietly. When at least one image in the period
contains a person, a graph of the last 48 hours of person counts is rendered and
sent via ``telegram-send``.

When ``--date YYYY-MM-DD`` is provided, the script queries InfluxDB for times on
that date where a person was detected and sends mosaics of the corresponding
images via telegram, annotating each tile with its capture time.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List

import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont
from influxdb import InfluxDBClient
from rich.console import Console
from rich.progress import Progress
from ultralytics import YOLO

console = Console()


# Paths and configuration ----------------------------------------------------
MOTION_DIR = Path("/var/lib/motion")
PEOPLE_GRAPH = Path("/tmp/person_count.png")

INFLUX_HOST = os.getenv("INFLUX_HOST", "localhost")
INFLUX_PORT = int(os.getenv("INFLUX_PORT", "8086"))
INFLUX_USER = os.getenv("INFLUX_USER", "admin")
INFLUX_PASSWORD = os.getenv("INFLUX_PASSWORD", "admin")
INFLUX_DB = os.getenv("INFLUX_DB", "motion")


# Utility functions ----------------------------------------------------------
def ensure_influx_running() -> None:
    """Start the InfluxDB service if it is not running."""
    running = subprocess.run(
        ["pgrep", "-f", "influxd"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode
    if running != 0:
        subprocess.run(
            ["systemctl", "start", "influxdb"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(5)


def ensure_database(client: InfluxDBClient, name: str) -> None:
    """Create database ``name`` in InfluxDB if it does not exist."""
    existing = {db["name"] for db in client.get_list_database()}
    if name not in existing:
        client.create_database(name)


def timestamp_from_filename(path: Path) -> datetime:
    """Return ``datetime`` encoded in ``path`` or fall back to ``mtime``."""
    match = re.search(r"(\d{8})[_-](\d{6})", path.name)
    if match:
        dt_str = match.group(1) + match.group(2)
        try:
            return datetime.strptime(dt_str, "%Y%m%d%H%M%S")
        except ValueError:
            pass
    return datetime.fromtimestamp(path.stat().st_mtime)


def recent_images(minutes: int = 30) -> Dict[Path, datetime]:
    """Return mapping of images within the last ``minutes`` to their timestamp."""
    cutoff = datetime.now() - timedelta(minutes=minutes)
    images: Dict[Path, datetime] = {}
    for entry in os.scandir(MOTION_DIR):
        if not entry.is_file():
            continue
        if not entry.name.lower().endswith((".jpg", ".jpeg")):
            continue
        path = Path(entry.path)
        ts = timestamp_from_filename(path)
        if ts >= cutoff:
            images[path] = ts
    return images


def cpu_temperature() -> float:
    """Return the current CPU temperature in Celsius."""
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return int(f.read().strip()) / 1000.0
    except FileNotFoundError:  # pragma: no cover - platform specific
        return 0.0


def wait_for_cool_cpu(max_temp: float = 60.0, cool_temp: float = 55.0) -> None:
    """Print CPU temperature and delay if above ``max_temp`` until below ``cool_temp``."""
    temp = cpu_temperature()
    console.print(f"CPU temperature: {temp:.1f}°C")
    if temp > max_temp:
        while temp > cool_temp:
            time.sleep(5)
            temp = cpu_temperature()
            console.print(f"CPU temperature: {temp:.1f}°C")


def detect_people(model: YOLO, image_paths: Iterable[Path]) -> Dict[Path, int]:
    """Return number of detected persons for each image."""
    paths = list(image_paths)
    counts: Dict[Path, int] = {}
    with Progress() as progress:
        task = progress.add_task("Detecting people", total=len(paths))
        for path in paths:
            wait_for_cool_cpu()
            results = model(str(path))
            persons = sum(1 for c in results[0].boxes.cls if int(c) == 0)
            counts[path] = persons
            progress.print(str(path))
            progress.advance(task)
    return counts


def write_counts(
    client: InfluxDBClient, counts: Dict[Path, int], times: Dict[Path, datetime]
) -> None:
    """Store person counts in InfluxDB using supplied timestamps."""
    points = []
    for path, num in counts.items():
        ts = times.get(path, datetime.utcfromtimestamp(path.stat().st_mtime))
        points.append(
            {
                "measurement": "person_count",
                "tags": {"source": "motion"},
                "time": ts.isoformat() + "Z",
                "fields": {"count": num},
            }
        )
    if points:
        client.write_points(points)


def generate_graph(client: InfluxDBClient, output: Path) -> Path:
    """Create a 48 hour graph of person counts."""
    query = (
        'SELECT "count" FROM "person_count" WHERE time > now() - 48h'
    )
    result = client.query(query)
    points = list(result.get_points(measurement="person_count"))

    times: list[datetime] = []
    values: list[float] = []
    for p in points:
        times.append(datetime.fromisoformat(p["time"].replace("Z", "+00:00")))
        values.append(p["count"])

    if times and values:
        plt.figure()
        plt.plot(times, values, "o", linestyle="none")
        plt.title("person_count")
        plt.xlabel("time")
        plt.ylabel("value")
        plt.grid(True, linestyle="--", linewidth=0.5)
        plt.tight_layout()
        plt.savefig(output)
        plt.close()
    return output


def send_via_telegram(paths: Iterable[Path]) -> None:
    """Send files via telegram-send."""
    for path in paths:
        subprocess.run(["telegram-send", "-i", str(path)], check=True)


def query_person_times(client: InfluxDBClient, day: date) -> List[datetime]:
    """Return times on ``day`` where a person was detected."""
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)
    query = (
        f"SELECT \"count\" FROM \"person_count\" "
        f"WHERE time >= '{start.isoformat()}Z' AND time < '{end.isoformat()}Z' "
        "AND \"count\" > 0"
    )
    result = client.query(query)
    return [
        datetime.fromisoformat(p["time"].replace("Z", "+00:00"))
        for p in result.get_points(measurement="person_count")
    ]


def images_for_times(times: Iterable[datetime]) -> List[Path]:
    """Return image files matching the given timestamps."""
    images: List[Path] = []
    for ts in times:
        stamp = ts.strftime("%Y%m%d%H%M%S")
        images.extend(sorted(MOTION_DIR.glob(f"*{stamp}*.jpg")))
        images.extend(sorted(MOTION_DIR.glob(f"*{stamp}*.jpeg")))
    return images


def create_mosaic_with_times(
    image_paths: Iterable[Path], output: Path, cols: int = 4, rows: int = 4
) -> Path:
    """Create a mosaic annotating each tile with its capture time."""
    paths = list(image_paths)[: cols * rows]
    if not paths:
        raise ValueError("No images for mosaic")
    imgs = [Image.open(p) for p in paths]
    w, h = imgs[0].size
    mosaic = Image.new("RGB", (cols * w, rows * h))
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24
        )
    except OSError:  # pragma: no cover - font may be missing
        font = ImageFont.load_default()

    for idx, (img, path) in enumerate(zip(imgs, paths)):
        ts = timestamp_from_filename(path)
        text = ts.strftime("%Y-%m-%d %H:%M:%S")
        draw = ImageDraw.Draw(img)
        x, y = 10, 10
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx or dy:
                    draw.text((x + dx, y + dy), text, font=font, fill="black")
        draw.text((x, y), text, font=font, fill="white")
        x0 = (idx % cols) * w
        y0 = (idx // cols) * h
        mosaic.paste(img, (x0, y0))

    mosaic.save(output)
    return output


def process_date(day: date) -> None:
    """Send mosaics of all person detections for ``day`` via telegram."""
    ensure_influx_running()
    client = InfluxDBClient(
        host=INFLUX_HOST,
        port=INFLUX_PORT,
        username=INFLUX_USER or None,
        password=INFLUX_PASSWORD or None,
    )
    ensure_database(client, INFLUX_DB)
    client.switch_database(INFLUX_DB)
    times = query_person_times(client, day)
    client.close()
    if not times:
        return

    images = images_for_times(times)
    for idx in range(0, len(images), 16):
        group = images[idx : idx + 16]
        out = Path(f"/tmp/person_mosaic_{idx//16 + 1}.jpg")
        create_mosaic_with_times(group, out)
        send_via_telegram([out])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Process images for given date (YYYY-MM-DD)")
    args = parser.parse_args()

    if args.date:
        day = datetime.strptime(args.date, "%Y-%m-%d").date()
        process_date(day)
        return

    start_perf = time.perf_counter()
    recent = recent_images(30)
    if not recent:
        return

    model = YOLO("yolov8n.pt")
    counts = detect_people(model, recent.keys())

    ensure_influx_running()
    client = InfluxDBClient(
        host=INFLUX_HOST,
        port=INFLUX_PORT,
        username=INFLUX_USER or None,
        password=INFLUX_PASSWORD or None,
    )
    ensure_database(client, INFLUX_DB)
    client.switch_database(INFLUX_DB)
    write_counts(client, counts, recent)

    any_person = any(num > 0 for num in counts.values())
    if any_person:
        generate_graph(client, PEOPLE_GRAPH)
        send_via_telegram([PEOPLE_GRAPH])

    client.close()
    console.print(f"Elapsed time: {time.perf_counter() - start_perf:.2f}s")


if __name__ == "__main__":
    main()

