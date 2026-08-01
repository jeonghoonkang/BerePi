#!/usr/bin/env python3
"""Extract text from one PNG image in input/."""

from image_text_extractor import run_image_cli


if __name__ == "__main__":
    raise SystemExit(run_image_cli(".png", "PNG 그림에서 문자를 추출합니다."))
