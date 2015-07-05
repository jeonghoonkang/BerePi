# -*- coding: utf-8 -*-
# monitor.py

import platform
import sys
import os
import time
import traceback
import requests
import RPi.GPIO as GPIO
from socket import gethostname

hostname =  gethostname()
SERVER_ADDR = '211.184.76.80'

GPIO.setwarnings(False)
GPIO.cleanup()
GPIO.setmode(GPIO.BCM)
GPIO.setup(19,GPIO.OUT)  # for LED indicating
GPIO.setup(26, GPIO.OUT) # for LED indicating

def query_last_data_point(bridge_id):
	url = 'http://%s/api/raw_bridge_last/?bridge_id=%d' % (SERVER_ADDR, bridge_id)
	
	try:
		ret = requests.get(url, timeout=10)
		if ret.ok:
			ctx = ret.json()
			if ctx['code'] == 0:
				return ctx['result']['time'], ctx['result']['value']

	except Exception:
		#print Exception
		pass
	return None
	
bridge_id = int(hostname[5:10])
GPIO.output(26, True) # server connection is OK, showing through LED

while True:
    ret = query_last_data_point(bridge_id)
    if ret is not None:
        t, v = ret
        if t > time.time() - 30:
            dt = time.time() - t 
            GPIO.output(19, True)
            GPIO.output(26, False)
        else:
            GPIO.output(19, True)
            GPIO.output(26, True)
    else:
        GPIO.output(19, False)
        GPIO.output(26, True)
    time.sleep(5.0)

