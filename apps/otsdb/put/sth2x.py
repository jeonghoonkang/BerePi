#!/usr/bin/python
# Author : jeonghoonkang, https://github.com/jeonghoonkang

devel_dir="/home/pi/devel"
tmp_dir=devel_dir+"/BerePi/apps"

from types import *
import sys
from time import strftime, localtime
import datetime
import requests
import json
import subprocess

sys.path.append(tmp_dir+"/sht20")
from sht25class import *

################
url = "http://10.0.0.43:4242/api/put"

def otsdb_restful_put():
    sht21_temp = temp_chk()
    temp_v=str(sht21_temp)
    if temp_v != "-100" :
    	print('otsdb %-5.2f `C' % (sht21_temp))
    ret = humi_chk()
    retstr = str(ret)
    if retstr != "-100" :
        print('otsdb %-5.2f %%' % (ret))

    #sname = hostname_chk()
    sname = "kang-odesk-03"
    data = {
        "metric": "z_beta.temp.sht2x.dgree",
        "timestamp": time.time(),
        "value": sht21_temp, #integer
        "tags": {
            #"eth0": macAddr,
            #"stalk": "VOLOSSH" ,
            "sensor" : "sht2x",
	        "name" : sname,
	        "floor_room": "6F_office",
	        "building": "global_rnd_center",
	        "owner": "kang",
	        "country": "kor"
        }
	#tags should be less than 9, 8 is alright, 9 returns http error
    }

    try :
        ret = requests.post(url, data=json.dumps(data))
    except requests.exceptions.Timeout :
        logger.error("http connection error, Timeout  %s", ret)
        pass 
    except requests.exceptions.ConnectionError :
        logger.error("http connection error, Too many requests %s")
        pass

    return

def temp_chk():
    temperature = getTemperature()
    return temperature

def humi_chk():
    humidity = getHumidity()
    return humidity

def hostname_chk():
    cmd = "hostname"
    return run_cmd(cmd)

# check it, which is not running , thus cancel calling it
def run_cmd(cmd):
    p = Popen(cmd, shell=True, stdout=PIPE)
    output = p.communicate()[0]
    return output

    
