# -*- coding: utf-8 -*-

import os
import sys
import time
import datetime

while(1):
    print os.system('sudo sh wifi_cron.sh')
    #print os.system('grep CRON /var/log/syslog')
    print datetime.datetime.now()   
    time.sleep(300)
