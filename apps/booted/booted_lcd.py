#Author : jeonghoonkang https://github.com/jeonghoonkang

import sys
import subprocess

sys.path.append("../lcd_berepi/lib")
from lcd import *

if __name__== "__main__" :
  lcd_init()
  LCDoff()

  pinkLCDon()
  yellowLCDon()
  whiteLCDon()

  str = subprocess.check_output("hostname",shell=True)
  str = str[:-1]
  lcd_string('Booted' ,LCD_LINE_1,1)
  lcd_string('%s ' % (str),LCD_LINE_2,1)
  time.sleep(1.5)


