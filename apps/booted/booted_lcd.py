#Author : jeonghoonkang https://github.com/jeonghoonkang

import sys
import subprocess
berePi_dir="/home/pi/devel/BerePi"
tmp_dir=berePi_dir + "/apps/lcd_berepi/lib"
sys.path.append(tmp_dir)
from lcd import *

def wip_chk():
    cmd = "ip addr show wlan0 | grep inet | awk '{print $2}' | cut -d/ -f1"
    wipAddr = run_cmd(cmd)
    return wipAddr

def run_cmd(cmd):
    p = Popen(cmd, shell=True, stdout=PIPE)
    output = p.communicate()[0]
    output = output[:-1]
    return output

if __name__== "__main__" :
  
  print tmp_dir
  
  lcd_init()
  LCDoff()

  pinkLCDon()
  yellowLCDon()
  whiteLCDon()

  str = subprocess.check_output("hostname",shell=True)
  str = str[:-1]
  lcd_string('Booted %s ' % (str) ,LCD_LINE_1,1)
  
  str = wip_chk()
  if str:
    lcd_string('%s WL     ' % (str),LCD_LINE_2,2)
  else :
    lcd_string('no Wi-Fi IP ',LCD_LINE_2,2)

  time.sleep(3.5)

