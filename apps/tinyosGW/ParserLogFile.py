#!/usr/bin/python

import re

#LOGFILE = "*.log"
LOGFILE = "/home/pi/rpi_log.log"
PATTERN = re.compile("\[INFO\] (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) > (.+)\n", re.DOTALL)
RPIINFO = ['HOSTNAME', 'IP', 'HDD', 'FREE MEM', 'CPU(\(.+\))', 'MEM(\(.+\))']

CNT = 0

f = open(LOGFILE,"r")
tmp_str = ''
rpi_info_list = []

lines = f.readlines()
for line in lines:
    if PATTERN.search(line):
        CNT+=1
        rpi_info = re.split(PATTERN, line)
	#if len(tmp_str) > 0: print "++++++++++\n" + tmp_str + "\n++++++++++"
	if len(tmp_str) > 0: rpi_info_list.append(tmp_str)
	tmp_str = ''
    else:
        rpi_info = [info for info in rpi_info if len(info) > 0]
	tmp_str += line
print CNT
print rpi_info_list

f.close()
