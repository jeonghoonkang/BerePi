# -*- coding: utf-8 -*-

# Author : https://github.com/jeonghoonkang

from __future__ import print_function
from time import gmtime, strftime
import os

myhost = os.uname()[1]

_t = strftime("%Y-%m-%d %H:%M:%S", gmtime()) + ' : ' + myhost
filename = 'doole_log' + myhost + '.txt'

# Mac OSX
#with open('/Users/tinyos/devel/BerePi/apps/log_check/output/' + filename , 'w') as outfile:

# RaspberryPi
with open('/home/pi/devel/BerePi/apps/log_check/output/' + filename , 'w') as outfile:
    outfile.write(_t + '\n')
