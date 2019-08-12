# -*- coding: utf-8 -*-

# Author : https://github.com/jeonghoonkang

from __future__ import print_function
from time import gmtime, strftime
import datetime
import os

myhost = os.uname()[1]

utc_time = datetime.datetime.utcnow()
kor_time = datetime.datetime.now()
time_diff = kor_time - utc_time 

_t = kor_time.strftime('%Y-%m-%d %H:%M:%S') + ' : ' + myhost 
#_t = strftime("%Y-%m-%d %H:%M:%S", kor_time) + ' : ' + myhost
filename = 'doodle_log' + myhost + '.txt'

# Mac OSX
#with open('/Users/tinyos/devel/BerePi/apps/log_check/output/' + filename , 'w') as outfile:

# RaspberryPi
with open('/home/pi/devel/BerePi/apps/log_check/output/' + filename , 'w') as outfile:
    outfile.write(_t + '\n')
    print (_t)
