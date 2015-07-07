#!/usr/bin/python
# Author : ipmstyle, https://github.com/ipmstyle
#        : jeonghoonkang, https://github.com/jeonghoonkang

# for the detail of HW connection, see lcd_connect.py

import sys
sys.path.append("./lib")
from lcd import *
sys.path.append("../sht20")
from sht25 import *


def main():
  # Initialise display
  lcd_init()
  print ip_chk(), wip_chk(), mac_chk(), wmac_chk(), stalk_chk()

  while True:
    lcd_string('Temperature & IP addr', LCD_LINE_1,1)
    lcd_string('MAC eth0, wlan0',LCD_LINE_2,1)
    blue_backlight(False) #turn on, yellow
    time.sleep(2.5) # 3 second delay

    str = temp_chk()
    #str = str[:-1]
    lcd_string('Temperature' ,LCD_LINE_1,1)
    lcd_string('%.5s `C' % (str),LCD_LINE_2,1)
    yellowLCDon()
    time.sleep(2) # 5 second delay

    str = ip_chk()
    str = str[:-1]
    lcd_string('%s ET' %str,LCD_LINE_1,1)
    str = mac_chk()
    str = str[:-1]
    lcd_string('%s' % (str),LCD_LINE_2,1)
    green_backlight(False) #turn on, yellow
    time.sleep(3.5) # 3 second delay

    str = wip_chk()
    str = str[:-1]
    lcd_string('%s WL     ' % (str),LCD_LINE_1,1)
    str = wmac_chk()
    str = str[:-1]
    lcd_string('%s' % (str),LCD_LINE_2,1)
    yellowLCDon()
    time.sleep(3.5) # 5 second delay
        
    str = stalk_chk()
    str = str[:-1]
    lcd_string('sTalk Channel' ,LCD_LINE_1,1)
    lcd_string('%s           ' % (str),LCD_LINE_2,1)
    time.sleep(3.5) # 5 second delay


def run_cmd(cmd):
    p = Popen(cmd, shell=True, stdout=PIPE)
    output = p.communicate()[0]
    return output

def temp_chk():
    temperature = getTemperature()
    return temperature

def ip_chk():
    cmd = "ip addr show eth0 | grep inet | awk '$2 !~ /^169/ {print $2}' | cut -d/ -f1"
    ipAddr = run_cmd(cmd)
    return ipAddr

def wip_chk():
    cmd = "ip addr show wlan0 | grep inet | awk '{print $2}' | cut -d/ -f1"
    wipAddr = run_cmd(cmd)
    return wipAddr

def mac_chk():
    cmd = "ifconfig -a | grep ^eth | awk '{print $5}'"
    macAddr = run_cmd(cmd)
    return macAddr

def wmac_chk():
    cmd = "ifconfig -a | grep ^wlan | awk '{print $5}'"
    wmacAddr = run_cmd(cmd)
    return wmacAddr

def stalk_chk():
    cmd = "hostname"
    return run_cmd(cmd)

if __name__ == '__main__':

  try:
    main()
  except KeyboardInterrupt:
    pass
  finally:
    lcd_byte(0x01, LCD_CMD)
    lcd_string("Goodbye!",LCD_LINE_1,2)
    GPIO.cleanup()
