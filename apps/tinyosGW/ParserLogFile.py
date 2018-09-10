#!/usr/bin/python

import re

#LOGFILE = "*.log"
LOGFILE = "/home/pi/rpi_log.log"
PATTERN = re.compile("\[INFO\] (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) > (.+)\n", re.DOTALL)
RPIINFO = ['HOSTNAME', 'IP', 'HDD', 'FREE MEM', 'CPU(\(.+\))', 'MEM(\(.+\))']

CNT = 0

f = open(LOGFILE,"r")

lines = f.readlines()
for line in lines:
    if PATTERN.search(line):
        CNT+=1
        rpi_info = re.split(PATTERN, line)
    else:
        #rpi_info.append(line)
        rpi_info = [info for info in rpi_info if len(info) > 0]
        print rpi_info
print CNT

f.close()
