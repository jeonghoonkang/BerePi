
### in case of below error
  - UnicodeDecodeError: 'ascii' codec can't decode byte 0xec in position 6: ordinal not in range(128)

### include utf-8 encoding
  - There is many things to do, not the one thing is solution for all error
    - vim /usr/lib/python2.7/sitecustomize.py
      - import sys
      - sys.setdefaultencoding("utf-8")
    - or just add in the __main__

### excel file handling
  - extract, compare, search
  - edit special cells and boxes


