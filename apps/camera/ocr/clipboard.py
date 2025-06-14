import argparse
import cv2
import pytesseract
import numpy as np
from PIL import ImageGrab


def image_from_clipboard():
    """Grab image data from the clipboard."""
    image = ImageGrab.grabclipboard()
    if isinstance(image, list):
        # Some systems return a list of file paths
        if image:
            return cv2.imread(image[0])
    elif image is not None:
        # PIL Image returned
        image = image.convert("RGB")
        return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    return None


def ocr_image(image, lang="eng"):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    text = pytesseract.image_to_string(gray, lang=lang)
    return text


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract text from an image in the clipboard")
    parser.add_argument("-l", "--lang", default="kor", help="Tesseract language code, e.g. 'eng' or 'kor'")
    args = parser.parse_args()

    img = image_from_clipboard()
    print(img)
    if img is None:
        raise RuntimeError("No image found in clipboard")

    text = ocr_image(img, lang=args.lang)
    print(text.strip())
    print(text.split())