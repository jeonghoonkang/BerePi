## OCR application
- open png file and run OCR
- get String from image
### How to run code
- python3 easyocr_run.py -f sample.jpg -lang ko

### installation and error
* 에러
  - AttributeError: module 'PIL.Image' has no attribute 'Resampling'
* 해결 
  - sudo pip3 install git+https://github.com/JaidedAI/EasyOCR.git --force
