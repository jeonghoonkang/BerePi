
import pytesseract
# sudo apt update
# sudo apt install tesseract-ocr
# sudo apt install libtesseract-dev

import cv2
# pip3 install opencv-python
# print(cv2.getVersionString())

### ~/devel/data/ocr/sample_receipt.png 
import matplotlib
import os

image = cv2.imread(os.path.expanduser('~/devel/data/ocr/sample_receipt.png'))
rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
text = pytesseract.image_to_string(rgb_image)

print (text)


## info for Korean OCR
### https://github.com/yunwoong7/korean_ocr_using_pororo


## try out the following
### https://weejw.tistory.com/611
