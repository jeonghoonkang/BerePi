#!/usr/bin/python
# Author : jeonghoonkang, https://github.com/jeonghoonkang

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

################
sht21_temp = temp_chk()
temp_v=str(sht21_temp)
if temp_v != "-100" :
    print('Here %-5.2f `C' % (sht21_temp))
ret = humi_chk()
retstr = str(ret)
if retstr != "-100" :
    print('Here %-5.2f %%' % (ret))

def temp_chk():
    temperature = getTemperature()
    return temperature

def humi_chk():
    humidity = getHumidity()
    return humidity

  
