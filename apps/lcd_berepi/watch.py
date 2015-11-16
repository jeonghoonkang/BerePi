#!/usr/bin/python
# Author : ipmstyle, https://github.com/ipmstyle
#        : jeonghoonkang, https://github.com/jeonghoonkang
# for the detail of HW connection, see lcd_connect.py

import sys
from time import strftime, localtime
sys.path.append("./lib")
from lcd import *
sys.path.append("../sht20")
from sht25class import *

import datetime
import requests
import json
import subprocess
import argparse

devel_dir="/home/pi/devel"
tmp_dir=devel_dir+"/danalytics/thingsweb/weblib/recv"
sys.path.append(tmp_dir)
from lastvalue import *

def parse_args():
    parser=argparse.ArgumentParser(description="how to run, watch.py", usage='use "%(prog)s --help" for more information', formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-ip", "--ipaddress", default="0.0.0.0:0000", help="input ip address of iot db")
    args = parser.parse_args()
    return args

def main():
  arg = parse_args()

  # Initialise display
  lcd_init()
  print ip_chk(), wip_chk(), mac_chk(), wmac_chk(), stalk_chk(), time_chk()

  dbip = arg.ipaddress
  if dbip == "0.0.0.0:0000" :
      print "  please input ip address of iot DB"
      print "  It will run without restful get API"
      dbip = "no_db"

  while True:

    tstr = time_chk()
    lcd_string('%s' % (tstr),LCD_LINE_1,1)
    str = temp_chk()
    lcd_string('%.5s `C' % (str),LCD_LINE_2,1)
    whiteLCDon()
    time.sleep(3) 

    str = ip_chk()
    str = str[:-1]
    lcd_string('%s ET' %str,LCD_LINE_1,1)
    str = mac_chk()
    str = str[:-1]
    #lcd_string('%s' % (str),LCD_LINE_2,1)
    #blueLCDon()
    #time.sleep(0.5) 

    str = wip_chk()
    str = str[:-1]
    lcd_string('%s WL     ' % (str),LCD_LINE_2,1)
    str = wmac_chk()
    str = str[:-1]
    #lcd_string('%s' % (str),LCD_LINE_2,1)
    blueLCDon()
    time.sleep(1.2) 
        
    str = stalk_chk()
    str = str[:-1]
    lcd_string('%s' % (tstr),LCD_LINE_1,1)
    lcd_string('%s           ' % (str),LCD_LINE_2,1)
    blueLCDon()
    time.sleep(1) 

    # display time & CO2
    tstr = time_chk()
    lcd_string('%s' % (tstr),LCD_LINE_1,1)
    if dbip != "no_db":
        try: 
            co2str = get_last_value(dbip,'gyu_RC1_co2.ppm',{'nodeid':'920'})
            tmp = round(co2str[0], 2)
            print "CO2 Level = ", tmp, "ppm"
            lcd_string('%s ppm' %tmp, LCD_LINE_2,1)
        except:
            lcd_string('Restful API error', LCD_LINE_2,1)
          
    whiteLCDon()
    time.sleep(3) 

    lcd_string('%s' % (tstr),LCD_LINE_1,1)
    str = humi_chk()
    lcd_string('%.5s %%' % (str),LCD_LINE_2,1)
    whiteLCDon()
    time.sleep(2) 

def run_cmd(cmd):
    p = Popen(cmd, shell=True, stdout=PIPE)
    output = p.communicate()[0]
    return output

def temp_chk():
    temperature = getTemperature()
    return temperature

def humi_chk():
    humidity = getHumidity()
    return humidity

def time_chk():
    time = strftime("%Y-%m%d %H:%M", localtime())
    return time

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
    lcd_init()
    lcd_byte(0x01, LCD_CMD)
    lcd_string("Goodbye!",LCD_LINE_1,2)
    GPIO.cleanup()
