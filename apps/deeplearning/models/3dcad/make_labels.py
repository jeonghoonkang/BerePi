"""Create an editable label manifest from a CAD directory."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cad_dir", type=Path)
    parser.add_argument("output_csv", type=Path)
    args = parser.parse_args()
    extensions = {".step", ".stp", ".iges", ".igs", ".brep", ".brp"}
    files = sorted(p for p in args.cad_dir.rglob("*") if p.suffix.lower() in extensions)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f); writer.writerow(["file", "label"])
        writer.writerows((p.relative_to(args.cad_dir).as_posix(), 0) for p in files)
    print(f"Wrote {len(files)} rows to {args.output_csv}; edit the label column before training.")


if __name__ == "__main__":
    main()
