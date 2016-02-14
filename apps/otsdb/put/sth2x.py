#!/usr/bin/python
# Author : jeonghoonkang, https://github.com/jeonghoonkang

devel_dir="/home/pi/devel"
tmp_dir=devel_dir+"/BerePi/apps"

from types import *
import sys
from time import strftime, localtime
sys.path.append(tmp_dir+"/sht20")
from sht25class import *

import datetime
import requests
import json
import subprocess

################
url = "http://xxx.xxx.xxx.xxx/api/put"

def otsdb_restful_put():
    sht21_temp = temp_chk()
    temp_v=str(sht21_temp)
    if temp_v != "-100" :
    	print('Here %-5.2f `C' % (sht21_temp))
    ret = humi_chk()
    retstr = str(ret)
        if retstr != "-100" :
        print('Here %-5.2f %%' % (ret))
    hostname = hostname_chk()

    data = {
        "metric": "z_beta.temp.sht2x.dgree",
        "timestamp": time.time(),
        "value": sht21_temp, #integer
        "tags": {
            #"eth0": macAddr,
            #"stalk": "VOLOSSH" ,
            "sensor" : "sht2x",
	    "name" : hostname,
	    "floor_room": "6F_office",
	    "building": "global_rnd_center",
	    "owner": "kang",
	    "country": "kor"
	}
	#tags should be less than 9, 8 is alright, 9 returns http error
	try :
		ret = requests.post(url, data=json.dumps(data))
	except requests.exceptions.Timeout :
		logger.error("http connection error, Timeout  %s", ret)
		continue
	except requests.exceptions.ConnectionError :
		logger.error("http connection error, Too many requests %s")
		continue

def temp_chk():
    temperature = getTemperature()
    return temperature

def humi_chk():
    humidity = getHumidity()
    return humidity

def run_cmd(cmd):
    p = Popen(cmd, shell=True, stdout=PIPE)
    output = p.communicate()[0]
    return output

def hostname_chk():
    cmd = "hostname"
    return run_cmd(cmd)
    
