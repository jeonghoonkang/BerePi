# OCR Name Card Application

This is a simple OCR (Optical Character Recognition) application that is designed to extract text from name cards. It utilizes computer vision techniques to recognize and extract text from images of name cards.

## Features

- Image preprocessing: The application applies various image processing techniques to enhance the quality of the input image.
- Text extraction: The OCR algorithm is used to extract text from the preprocessed image.
- Text analysis: The extracted text is analyzed to identify relevant information such as name, phone number, email address, etc.
- Output formatting: The application formats the extracted information in a structured manner for easy readability.

## Installation

To run the OCR Name Card Application, follow these steps:

1. Python3
2. ocr reader source code of this repo 
3. for mac osx
  - brew install tesseract
  - brew reinstall tesseract
 

## Usage

1. Launch the application.
2. Upload an image of a name card.


## 구조
1. 모든 명함 이미지 파일 경로, 리스트로 만들기 (하위 디렉토리 포함) files
1. files 를 ocr을 거쳐, json 으로 생성
    1. 각 json은 단독 파일에 하나의 json field
1. 여러개 json을 포함한 dir에 대해서
    1. 모든 json 읽어서, 통합 json으로 생성
1. 메뉴얼 작업으로, 인식한 ocr 문자의 오류를 확인하여 필드에 정확히 작성
1. 메뉴얼 수정한 통합 json와, 새롭게 생성되는 통합 json을 비교하여, 메뉴얼 작업이 지워지지 않도록 체크 
