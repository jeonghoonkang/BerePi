# Author: Jeonghoon Kang, https://github.com/jeonghoonkang

import argparse
import cv2
import pytesseract
import numpy as np
import platform
import subprocess
from io import BytesIO
from PIL import Image
try:
    from PIL import ImageGrab  # available on Windows and macOS
except Exception:  # pragma: no cover - ImageGrab may not be built on Linux
    ImageGrab = None


def _from_windows_clipboard():
    image = ImageGrab.grabclipboard() if ImageGrab else None
    if isinstance(image, list):
        if image:
            return cv2.imread(image[0])
    elif image is not None:
        image = image.convert("RGB")
        return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    return None


def _from_linux_clipboard():
    try:
        data = subprocess.check_output(
            ["xclip", "-selection", "clipboard", "-t", "image/png", "-o"],
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return None
    try:
        image = Image.open(BytesIO(data)).convert("RGB")
    except Exception:
        return None
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def image_from_clipboard():
    """Grab image data from the clipboard on Windows or Linux."""
    system = platform.system()
    if system == "Windows":
        return _from_windows_clipboard()
    elif system == "Linux":
        return _from_linux_clipboard()
    else:
        return None


def ocr_image(image, lang="eng"):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    text = pytesseract.image_to_string(gray, lang=lang)
    return text


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract text from an image file or from the clipboard, windows or MacOS only. if use Ubuntu, use xclip to copy image to clipboard.",
    )
    parser.add_argument(
        "-f",
        "--file",
        help="path to an image file (falls back to clipboard if omitted)",
    )
    parser.add_argument(
        "-l",
        "--lang",
        default="kor",
        help="Tesseract language code, e.g. 'eng' or 'kor'",
    )
    args = parser.parse_args()

    if args.file:
        img = cv2.imread(args.file)
        if img is None:
            raise FileNotFoundError(f"Cannot read image '{args.file}'")
    else:
        img = image_from_clipboard()
        if img is None:
            raise RuntimeError("No image found in clipboard")

    text = ocr_image(img, lang=args.lang)
    print(text.strip())
    print(text.split())