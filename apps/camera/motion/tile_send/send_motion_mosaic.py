#!/usr/bin/env python3
"""Collect motion images from last three days, tile into one image, and send via telegram-send."""

from datetime import datetime, timedelta
from math import ceil, sqrt
from pathlib import Path
import subprocess

from PIL import Image

MOTION_DIR = Path("/var/lib/motion")
OUTPUT_FILE = Path("/tmp/motion_mosaic.jpg")

def gather_recent_images(directory: Path, days: int = 3):
    cutoff = datetime.now() - timedelta(days=days)
    images = []
    for ext in ("*.jpg", "*.jpeg", "*.png"):
        for path in directory.glob(ext):
            if datetime.fromtimestamp(path.stat().st_mtime) >= cutoff:
                images.append(path)
    return sorted(images)

def create_mosaic(image_paths, output_path: Path):
    if not image_paths:
        raise ValueError("No images to process")

    imgs = [Image.open(p) for p in image_paths]
    w, h = imgs[0].size

    cols = ceil(sqrt(len(imgs)))
    rows = ceil(len(imgs) / cols)
    mosaic = Image.new('RGB', (cols * w, rows * h))

    for idx, img in enumerate(imgs):
        x = (idx % cols) * w
        y = (idx // cols) * h
        mosaic.paste(img, (x, y))
    mosaic.save(output_path)
    return output_path

def send_via_telegram(image_path: Path):
    subprocess.run(['telegram-send', '--image', str(image_path)], check=True)

def main():
    images = gather_recent_images(MOTION_DIR)
    if not images:
        print("No recent images found.")
        return
    mosaic_path = create_mosaic(images, OUTPUT_FILE)
    send_via_telegram(mosaic_path)

if __name__ == "__main__":
    main()
