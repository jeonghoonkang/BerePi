#!/usr/bin/python

import re

LOGFILE = "*.log"
LOGFILE = "/home/pi/rpi_log.log"
PATTERN = re.compile("[INFO] (\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2}),(\d{3}) > ")
PATTERN = re.compile("[INFO] \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} >")
PATTERN = re.compile('[INFO]..\d{4}-\d{2}-\d{2}')
PATTERN = re.compile("\[INFO\] (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) > (.+)\n", re.DOTALL)

CNT = 0

f = open(LOGFILE,"r")


lines = f.readlines()
for line in lines:
    if PATTERN.search(line):
        CNT+=1
        print re.split(PATTERN, line)
print CNT


#data = f.read()
#print re.search(PATTERN, data)
#packet = re.split(PATTERN, data)

#for p in packet:
#    pass
    #print p
#print len(packet)
#print re.search(PATTERN, data)
#print packet.group(1)
f.close()
