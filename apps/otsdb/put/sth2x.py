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

'''url을 반드시 넣어줘야 합니다'''
#url = "http://10.0.0.43:4242/api/put"

def otsdb_restful_put_sht2x(_ip = None):

    sht21_temp = temp_chk()
    temp_v=str(sht21_temp)
    if temp_v != "-100" :
    	print('otsdb %-5.2f `C' % (sht21_temp))

    humi = humi_chk()
    humi_v = str(humi)
    if humi_v != "-100" :
        print('otsdb %-5.2f %%' % (humi))

    #ip_add = ip_chk()
    #sname = hostname_chk()
    sname = "kang-odesk-03"
    if _ip != None : ip_add = _ip
    else: ip_add = 'unkown'
    _time = time.time() 

    metric = "jkraspi.rc01.temp.degree"
    print "   ", url, metric, "IPadd=",ip_add

    data_temp = {
        "metric": metric ,
        "timestamp": _time,
        "value": sht21_temp, #integer
        "tags": {
            "IPadd": ip_add,
            #"stalk": "VOLOSSH" ,
            "sensor" : "sht2x",
	        "name" : sname,
	        "floor_room": "6F_office",
	        "building": "global_rnd",
	        "loc": "pangyo"
            #"owner": "kang"
        }
	#tags should be less than 9, 8 is alright, 9 returns http error
    }

    metric = "jkraspi.rc01.humi"
    print "   ", url, metric, "IPadd=",ip_add
    data_humi = {
        "metric": metric,
        "timestamp": _time,
        "value": humi, #integer
        "tags": {
            "IPadd": ip_add,
            #"stalk": "VOLOSSH" ,
            "sensor" : "sht2x",
	        "name" : sname,
	        "floor_room": "6F_office",
	        "building": "global_rnd",
	        "loc": "pangyo"
            #"owner": "kang"
        }
	#tags should be less than 9, 8 is alright, 9 returns http error
    }

    try :
        ret = requests.post(url, data=json.dumps(data_temp))
        print ret
        ret = requests.post(url, data=json.dumps(data_humi))
        print ret
    except requests.exceptions.Timeout as e:
        #logger.error("http connection error, Timeout  %s", ret)
        print("http connection error, Timeout  %s", e)
        pass 
    except requests.exceptions.ConnectionError as e :
        print("http connection error, Timeout  %s", e)
        #logger.error("http connection error, Too many requests %s")
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

def run_cmd(cmd):
    p = Popen(cmd, shell=True, stdout=PIPE)
    output = p.communicate()[0]
    return output


