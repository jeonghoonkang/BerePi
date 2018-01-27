# -*- coding: utf-8 -*-
# Author : jeonghoonkang, https://github.com/jeonghoonkang 

import httplib
import time
from time import strftime, localtime

hue_uid = "c274b3c285d19cf3480c91439329147"
restcmd = "/api"+hue_uid+"/lights"

str = " "
ip='10.255.255.65x'
latest_time = "initial status"
xhue = [10000,25000,46000,56280]
def shifthue() :
    global str
    global xhue
    global latest_time
    xhue.insert(0,xhue[-1])
    xhue = xhue[0:4] 
    #print xhue

    try :
        conn = httplib.HTTPConnection(ip)
    except :
        print "fail to connect to Hue GW..."
        return
    
    callurl = restcmd + "/4/state"
    """
    try:
        conn.request("PUT",callurl ,'{"on":false}')
        response = conn.getresponse()
        data = response.read()
    except:
        print "keep goging...."
        time.sleep(4)
    time.sleep(1)
    """
    for num in [4,3,2,1] :
        callurl = restcmd + "/%s/state"%(num)
        #print callurl
        huenumber = (xhue[4-num])

        try :
            conn.request("PUT",callurl ,'{"on":false}')
            response = conn.getresponse()
            data = response.read()
            time.sleep(1)

            conn.request("PUT",callurl ,'{"on":true, "sat":254, "bri":254, "hue":%s}'%huenumber)
            response = conn.getresponse()
            data = response.read()
            #print data
            time.sleep(1)
        
            latest_time = time_chk()

        except (httplib.HTTPException) as e :
            print latest_time, "HTTPException", e.args[0]
            time.sleep(4)
            conn = httplib.HTTPConnection(ip)
            #지속적으로 http exception 발생시 email 로 통보 

        finally :
            #print latest_time, "Finally"
            time.sleep(0.3)
            conn = httplib.HTTPConnection(ip)

def time_chk():
    time = strftime("%Y-%m%d %H:%M",localtime())
    return time

def hue4on():
	global str
	conn.request("PUT",restcmd+"/4/state", '{"on":true}')
	response = conn.getresponse()
	data = response.read()
	str = data + '<br>'
	time.sleep(2)
	return web()

def hue4off():
	global str
	conn.request("PUT",restcmd+"/4/state", '{"on":false}')
	response = conn.getresponse()
	data = response.read()
	str = data + '<br>'
	time.sleep(2)
	return web()

if __name__ == "__main__": 
#   print web()
    while True :
        shifthue()
        time.sleep(5)

