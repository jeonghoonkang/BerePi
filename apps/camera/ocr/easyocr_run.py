import easyocr

fpath='~/devel/data/ocr/sample_receipt.png'
#(os.path.expanduser('~/devel/data/ocr/sample_receipt.png'))

reader = easyocr.Reader(['ko','en'])
result = reader.readtext(fpath)

print(result)

