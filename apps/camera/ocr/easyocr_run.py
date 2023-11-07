# Author : https://github.com/jeonghoonkang
# have to use python3.8 

import easyocr
from pprint import pprint
import os, sys
import argparse

argparser = argparse.ArgumentParser()
argparser.add_argument('-lang', '--language', help='language, ko, ja', default='ko')
argparser.add_argument('-f', '--file', help='file name', default='./sample.jpg')
args = argparser.parse_args()

file_name = args.file
language = args.language
print(language)
print (file_name)

reader = easyocr.Reader(['en',language]) #language is changing string

chk_string = ["ko","ja"]
#for chk in chk_string:
    #print (chk)

if (not any( chk in language for chk in chk_string)): # if language is not in chk_string:
    print (language)
    print ("language is not in ko, ja")
    sys.exit("language mismatch")
    
print (file_name, language)
fpath = file_name

#fpath='/home/tinyos/devel_opment/data/ocr/sample_receipt.png'

reader = easyocr.Reader([language,'en']) #language

#print (sys.argv)

result = reader.readtext(fpath)

pprint(result, depth=5, indent=4)

