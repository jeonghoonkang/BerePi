# -*- coding: utf-8 -*-
# Author : https://github.com/jeonghoonkang
# this software needs library of lastvalue, which is in the commercial RaspberryPi (volovlu.com)

import datetime
import requests
import json

import sys
import subprocess
devel_dir="/home/pi/devel"
tmp_dir=devel_dir + "/danalytics/thingsweb/weblib/recv"
sys.path.append(tmp_dir)
from lastvalue import *

if __name__ == '__main__':
    para1 = 'gyu_RC1_co2.ppm'
    para2 = {'nodeid':arg2}
    print get_last_value(arg1, str(para1), para2)
