#!/usr/bin/python

import re

LOGFILE = "*.log"
LOGFILE = "/home/pi/rpi_log.log"
PATTERN = re.compile("[INFO] (\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2}),(\d{3}) > ")
PATTERN = re.compile("[INFO] \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} >")
PATTERN = re.compile("[INFO] [0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}")
#FORAMT = '[INFO] (\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2}),(\d{3}) > HOSTNAME : [hostname]\n'.format({'h': 16, 'm': 30, 's': 0})
#FORAMT = '[INFO] (\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2}),(\d{3}) > HOSTNAME : [hostname]\n'.format({'h': 16, 'm': 30, 's': 0})

CNT = 0

f = open(LOGFILE,"r")

'''
lines = f.readlines()
for line in lines:
    if PATTERN.search(line):
        CNT+=1
        print re.split(PATTERN, line)
'''

data = f.read()
packet = re.split(PATTERN, data)

for p in packet:
    print p
print len(packet)
print re.search(PATTERN, data)
#print packet.group(1)
f.close()
