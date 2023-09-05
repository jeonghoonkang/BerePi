# Author : https://github.com/jeonghoonkang
# have to use python3.8 

import easyocr
from pprint import pprint

fpath='/home/tinyos/devel_opment/data/ocr/sample_receipt.png'

#(os.path.expanduser('~/devel/data/ocr/sample_receipt.png'))

reader = easyocr.Reader(['ko','en'])
result = reader.readtext(fpath)

pprint(result, depth=2, indent=4)

