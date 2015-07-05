#Author : jeonghoonkang https://github.com/jeonghoonkang

import sys
sys.path.append("./lib")
from lcd import *

if __name__== "__main__" :
  lcd_init()
  LCDoff()
  pinkLCDon()
  yellowLCDon()
  str = "Yellow?"
  while True :
    lcd_string('Print Test' ,LCD_LINE_1,1)
    lcd_string('%s' % (str),LCD_LINE_2,1)
    time.sleep(1.5)

