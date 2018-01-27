import serial,os,time
import sys
#import RPi.GPIO as GPIO
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
ppm = 777
import urllib
try:
    import http.client as http_client
except ImportError:
    import httplib as http_client

http_client.HTTPConnection.debuglevel = 1


logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True

# important, sensorname shuould be pre-defined, unique sensorname
sensorname = "KETI_1"

url = "http://211.148.192.211:8000/svc/PointService.asmx/SetPointValue"

#def getHwAddr(ifname):
#	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#	info = fcntl.ioctl(s.fileno(), 0x8927, struct.pack('256s', ifname[:15]))
#	return ':'.join(['%02x' %ord(char) for char in info[18:24]])

macAddr = 'eth0'

#logger = logging.getLogger(sensorname)
#logger.setLevel(logging.DEBUG)
#formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#s
#fileHandler = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=FILEMAXBYTE,backupCount=10)
#fileHandler.setLevel(logging.DEBUG)
#fileHandler.setFormatter(formatter)
#logger.addHandler(fileHandler)

#try:
logline = sensorname + ' log ' + str(ppm) + ' ppm'  

params = urllib.urlencode({'value': 7})

#headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
#headers = {'Content-type': 'application/x-www-form-urlencoded'}
headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Accept':'text/plain'}

data = {
	#"metric": 'keti' ,
	#"timestamp": 'tea',
	"value": '0'
#	"tags": {
#		"hw": "raspberrypi2" ,
#		"sensor" : "sensor.xxx",
#		"name" : sensorname,
#		"floor_room": "10fl_min_room",
#        "zone":"1st zone",
#		"building": "name",
#		"owner": "me",jjjj
#		"country": "kor"
#	}
		#tags should be less than 9, 8 is alright, 9 returns http error
}
print data
print headers
#conn = httplib.HTTPConnection("211.148.192.211:8000")
#conn.request("POST", "/svc/PointService.asmx/SetPointValue",params,headers)
ret = requests.post(url, data=json.dumps(data), headers=headers)
print ret.text
#ret = requests.post(url, data=data, headers=headers)
#ret = conn.getresponse()
print ret.status, response.reason

#except requests.exceptions.Timeout :
#except requests.exceptions.ConnectionError :
#    logger.info("%s",logline)





