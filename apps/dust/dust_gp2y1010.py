# -*- coding: utf-8 -*-
# Author : Jeonghoonkang, github.com/jeonghoonkang

import time
import sys
#import adc_mcp3008 
sys.path.append("../adc")
sys.path.append("../../../../thingsweb/weblib/recv")
sys.path.append("../../../log_lib")
from adc_mcp3008 import *
from lastvalue import *
from raspi_log import *
import requests, json
import fcntl, socket, struct
import RPi.GPIO as GPIO

# Please check pin number of MCP3008
# 19 - CLK, 23 - MISO, 24 - MOSI, 25 - CS
# if you want to use, modify ../adc/adc_mcp3008
#def readadc(adcnum, clockpin, mosipin, misopin, cspin):
#    return adcout 
um = 0
sensorname = "dust.ws"
url = "http://xxx.xxx.xxx.xxx/api/put"

# HW setup, GPIO
# GIO PIN5
GPIO.setup(5, GPIO.OUT)
GPIO.output(5, False) # off 

adc_port = 0

def getHwAddr(ifname):
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	info = fcntl.ioctl(s.fileno(), 0x8927, struct.pack('256s', ifname[:15]))
	return ':'.join(['%02x' %ord(char) for char in info[18:24]])

macAddr = getHwAddr('eth0')
macAddr = macAddr.replace(':','.')

print "starting ...." 

loggerinit(sensorname)

while True : 
    # setup GPIO 5
    # set high GPIO 5
    GPIO.output(5, True)  # on 
    time.sleep(0.000175)  # 0.000280
    r = read(adc_port) 
    time.sleep(0.000000)  # 0.000040
    # set low GPIO 5
    GPIO.output(5, False) # off 
    time.sleep(0.009550)  # 0.009680

    if r > 187 :
        um = (500.0/2.9)*(3.3/1024)*r-103.44
    else :
        um = 0.1
    if r > 10 :
        print "r :",r

def sendit():
    data = {
        "metric": "rc1.dust.um",
        "timestamp": time.time(),
        "value": um,
        "tags": {
            "eth0": macAddr,
            "stalk": "VOLOSSH" ,
            "sensor" : "dust.gp2y",
            "name" : sensorname,
            "floor_room": "10fl_min_room",
            "building": "woosung",
            "owner": "kang",
            "country": "kor" }
        #tags should be less than 9, 8 is alright, 9 returns http error
    } 
    try : 
        ret = requests.post(url, data=json.dumps(data))
        print "http return : %s" %ret 
        logadd(r)
        logadd(um)
    except requests.exceptions.Timeout : 
        logerror("time out")
    except requests.exceptions.ConnectionError : 
        logerror("connection error")

    if  r > 0: 
        print "read : ", um


if __name__ == "__main__" :
    print "main
