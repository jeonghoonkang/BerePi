import serial,os,time
import sys
import RPi.GPIO as GPIO
import logging 
import logging.handlers
import json
import requests
import socket
import fcntl
import struct

debug_print = 1
FILEMAXBYTE = 1024 * 1024 * 100 #100MB
LOG_PATH = '/home/pi/log_tos.log'

level = 0
ppm = 0

# important, sensorname shuould be pre-defined, unique sensorname
sensorname = "sensor.001.xxx"

url = "http://xxx.x.xxx.xx:4xxx/api/put"

def getHwAddr(ifname):
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	info = fcntl.ioctl(s.fileno(), 0x8927, struct.pack('256s', ifname[:15]))
	return ':'.join(['%02x' %ord(char) for char in info[18:24]])

macAddr = getHwAddr('eth0')
macAddr = macAddr.replace(':','.')

logger = logging.getLogger(sensorname)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

fileHandler = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=FILEMAXBYTE,backupCount=10)
fileHandler.setLevel(logging.DEBUG)
fileHandler.setFormatter(formatter)
logger.addHandler(fileHandler)

	try:
	logline = sensorname + ' log ' + str(ppm) + ' ppm'  
	
	data = {
		"metric": sensorname ,
		"timestamp": time.time(),
		"value": ppm,
		"tags": {
			"eth0": macAddr,
			"hw": "raspberrypi2" ,
			"sensor" : "sensor.xxx",
			"name" : sensorname,
			"floor_room": "10fl_min_room",
			"building": "name",
			"owner": "name",
			"country": "kor"
		}
		#tags should be less than 9, 8 is alright, 9 returns http error
	}
		try :
			ret = requests.post(url, data=json.dumps(data))
		except requests.exceptions.Timeout :
		except requests.exceptions.ConnectionError :
logger.info("%s",logline)
	
