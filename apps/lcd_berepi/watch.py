#!/usr/bin/python
# Author : ipmstyle, https://github.com/ipmstyle
#        : jeonghoonkang, https://github.com/jeonghoonkang
# for the detail of HW connection, see lcd_connect.py

devel_dir="/home/pi/devel"
tmp_dir=devel_dir+"/BerePi/apps"

from types import *
import sys
from time import strftime, localtime
sys.path.append(tmp_dir+"/lcd_berepi/lib")
from lcd import *
sys.path.append(tmp_dir+"/sht20")
from sht25class import *

import datetime
import requests
import json
import subprocess
import argparse

tmp_dir=devel_dir+"/danalytics/thingsweb/weblib/recv"
sys.path.append(tmp_dir)
from lastvalue import *

def parse_args():
    parser=argparse.ArgumentParser(description="how to run, watch.py", usage='use "%(prog)s --help" for more information', formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-ip", "--ipaddress", default="0.0.0.0:0000", help="input ip address of iot db")
    parser.add_argument("-id", "--nodeid", default="-1", help="input id of iot device")
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

    # display local sensor : temperature
    tstr = time_chk()
    lcd_string('%s' % (tstr),LCD_LINE_1,1)
    sht21_temp = temp_chk()
    temp_v=str(sht21_temp)
    #assert type(temp_v) is StringType, "temp. variable is not an string: %s" %temp_v
    if temp_v != "-100" :
        lcd_string('Here %-5.2f`C' % (sht21_temp),LCD_LINE_2,1)
        whiteLCDon()
        time.sleep(3) 

    # display local sensor : humidity
    lcd_string('%s' % (tstr),LCD_LINE_1,1)
    ret = humi_chk()
    retstr = str(ret)
    #assert type(retstr) is StringType, "humi. variable is not an string: %s" %retstr
    if retstr != "-100" :
        lcd_string('Here %-5.2f %%' % (ret),LCD_LINE_2,1)
        whiteLCDon()
        time.sleep(2) 

    retstr = ip_chk()
    retstr = retstr[:-1]
    lcd_string('%s ET' %retstr,LCD_LINE_1,1)
    retstr = mac_chk()
    retstr = retstr[:-1]

    retstr = wip_chk()
    retstr = retstr[:-1]
    lcd_string('%s WL     ' % (retstr),LCD_LINE_2,1)
    retstr = wmac_chk()
    retstr = retstr[:-1]
    #lcd_string('%s' % (retstr),LCD_LINE_2,1)
    blueLCDon()
    time.sleep(1) 
        
    retstr = stalk_chk()
    retstr = retstr[:-1]
    lcd_string('%s' % (tstr),LCD_LINE_1,1)
    lcd_string('%s           ' % (retstr),LCD_LINE_2,1)
    blueLCDon()
    time.sleep(0.7) 

    # display time & Temperature
    tstr = time_chk()
    lcd_string('%s' % (tstr),LCD_LINE_1,1)
    if dbip != "no_db":
        sname="OUT"
        try: 
            temperaturestr = get_last_value(dbip,'gyu_RC1_thl.temperature',{'nodeid':'918'})
            tmp = round(temperaturestr[0], 2)
        except:
            lcd_string('Restful API error %s'%sname, LCD_LINE_2,1)
        print "%s Temperature = " %sname, tmp, "'C"
        lcd_string('%s %s `C' %(sname,tmp), LCD_LINE_2,1)
    whiteLCDon()
    time.sleep(2) 

    # display time & Temperature
    tstr = time_chk()
    lcd_string('%s' % (tstr),LCD_LINE_1,1)
    if dbip != "no_db":
        sname="MJrm"
        try: 
            temperaturestr = get_last_value(dbip,'gyu_RC1_thl.temperature',{'nodeid':'915'})
        except:
            lcd_string('Restful API error %s'%sname, LCD_LINE_2,1)
        tmp = round(temperaturestr[0], 2)
        print "%s Temperature = " %sname, tmp, "'C"
        lcd_string('%s %s `C' %(sname,tmp), LCD_LINE_2,1)
    whiteLCDon()
    time.sleep(2) 

    # display time & Temperature
    tstr = time_chk()
    lcd_string('%s' % (tstr),LCD_LINE_1,1)
    if dbip != "no_db":
        sname="LVrm"
        try: 
            temperaturestr = get_last_value(dbip,'gyu_RC1_thl.temperature',{'nodeid':'919'})
        except:
            lcd_string('Restful API error %s'%sname, LCD_LINE_2,1)
        tmp = round(temperaturestr[0], 2)
        print "%s Temperature = " %sname, tmp, "'C"
        lcd_string('%s %s `C' %(sname,tmp), LCD_LINE_2,1)
    whiteLCDon()
    time.sleep(2) 


    # display time & CO2
    tstr = time_chk()
    lcd_string('%s' % (tstr),LCD_LINE_1,1)
    if dbip != "no_db":
        sname="MJrm"
        try: 
            co2str = get_last_value(dbip,'gyu_RC1_co2.ppm',{'nodeid':'920'})
            tmp = round(co2str[0], 2)
            print "CO2 Level = ", tmp, "ppm"
            lcd_string('%s %s ppm' %(sname,tmp), LCD_LINE_2,1)
        except:
            lcd_string('Restful API error %s'%sname , LCD_LINE_2,1)
    color = int(tmp) 
    assert type(color) is IntType, "ppm variable is not an integer: %r" % id
    whiteLCDon()
    if (color > 1000) : 
        redLCDon()
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
