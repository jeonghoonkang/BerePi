import argparse
import cv2
import pytesseract
import difflib


def ocr_with_psm(image_path, oem=3, psm_range=range(14)):
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot read image '{image_path}'")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    results = {}
    for psm in psm_range:
        config = f" --oem {oem} --psm {psm}"
        text = pytesseract.image_to_string(gray, lang='kor+eng', config=config)
        results[psm] = text
    return results


def compare_results(results, baseline_psm=4):
    baseline = results.get(baseline_psm, "")
    comparisons = {}
    for psm, text in results.items():
        ratio = difflib.SequenceMatcher(None, baseline, text).ratio()
        comparisons[psm] = ratio
    return comparisons


def main():
    parser = argparse.ArgumentParser(description="Compare Tesseract OCR results for different PSM modes")
    parser.add_argument('-f', '--file', default='sample.jpg', help='Image file to test')
    args = parser.parse_args()

    results = ocr_with_psm(args.file)
    comparisons = compare_results(results)

    for psm in sorted(results.keys()):
        print(f"\nPSM {psm} result:\n{results[psm].strip()}")
        print('-' * 40)

    baseline_psm = 4
    print(f"\nSimilarity with baseline PSM {baseline_psm}:")
    for psm, ratio in sorted(comparisons.items()):
        print(f"PSM {psm}: {ratio:.2%}")


if __name__ == '__main__':
    main()
