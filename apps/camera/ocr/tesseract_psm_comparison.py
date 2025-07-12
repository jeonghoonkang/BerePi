import argparse
import cv2
import pytesseract
import difflib


def ocr_with_psm(image_path, oem=3, psm_range=range(14)):
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot read image '{image_path}'")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 3)

    results = {}
    for psm in psm_range:
        config = f" --oem {oem} --psm {psm}"
        try:
            text = pytesseract.image_to_string(gray, lang='kor+eng', config=config)
        except Exception as e:
            text = f"OCR Error: {e}"
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



#0  Orientation and script detection only (OSD only)  텍스트 인식 없이 방향과 언어만 감지
#1  Automatic page segmentation with OSD  전체 페이지 분석 + 방향 감지
#2  Automatic page segmentation, but no OSD  방향 감지 생략
#3  Fully automatic page segmentation (no OSD, no OCR engine specified)  페이지 전체 자동 분석 (가장 일반적인 디폴트)
#4  Assume a single column of text of variable sizes  단일 열 레이아웃 문서 (예: 기사, 문단)
#5  Assume a single uniform block of vertically aligned text  수직 정렬된 블록 (일본어 세로쓰기 등)
#6  Assume a single uniform block of text  단일 블록 텍스트 (양식, 명함, 전단 등)
#7  Treat the image as a single text line  단일 가로 줄 (예: OCR 스캔된 코드 라인)
#8  Treat the image as a single word  단일 단어 인식 (예: CAPTCHA, 짧은 문구)
#9  Treat the image as a single word in a circle  원형 마크 안의 글자 (희귀)
#10  Treat the image as a single character  문자 단위 OCR (글자별 인식 훈련 등)
#11  Sparse text. Find as much text as possible (no OSD).  드문드문한 텍스트 (레이블, 전자부품, 복잡한 UI)
#12  Sparse text with OSD  위와 같지만 방향 감지 포함
#13  Raw line. Treat image as a line, bypassing Tesseract layout analysis  전처리된 줄 기반 OCR (고정 폰트 등 특수 상황)