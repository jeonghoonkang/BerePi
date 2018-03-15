#!/usr/bin/python
#Author : jeonghoonkang, https://github.com/jeonghoonkang

# TO DO : add socket CLI commend
devel_dir="/home/pi/devel"
tmp_dir=devel_dir+"/BerePi/apps"

from types import *
import sys
import time
import datetime
import requests
import json
import subprocess


################################
# example : url = "http://10.0.0.43:4242/api/put"
# warning : we have to 50 JSON pack to put in OpenTSDB, on first stage.
#           if you add more, you shoud test amount of TX packets
################################

def otsdb_restful_put(url):
    sname = "kang-tinyos-test-000"
    toend = 101
    mname = "keti.tinyos.berepi.test"
    print "  metric name = ", mname
    for i in range(1,toend):
        val= i
        data = {
            "metric": mname,#alphabet and number . _ /
            "timestamp": time.time(),
            "value": val, #integer
            "tags": {
                #"eth0": macAddr,
                #"stalk": "VOLOSSH" ,
                "sensor" : "keti.put_test",
    	        "name" : sname,
            }
    	#tags should be less than 9, 8 is alright, 9 returns http error
        }

        try :
            ret = requests.post(url, data=json.dumps(data))
            # print "\n retrun is ", ret
            time.sleep (0.1)

            outstring = "  try %d / %d " % (i, toend-1) + "\r"
            sys.stdout.write(outstring)
            sys.stdout.flush()

        except requests.exceptions.Timeout :
            logger.error("http connection error, Timeout  %s", ret)
            pass
        except requests.exceptions.ConnectionError :
            logger.error("http connection error, Too many requests %s")
            pass
    return

def helpmsg():
    volubility = len(sys.argv)
    # merge list word items to one string line
    _stringargv = " ".join(sys.argv)

    print "\n  ********************************************** "
    print   "  *** TEST OpenTSDB insert                   *** "
    print   "  ***                             By 3POKang *** "
    print   "  ********************************************** "

    timestamp=time.localtime()

    print "  Thanks for the try, time : ", time.asctime(timestamp) , \
    " >> Volubility, Arg length = ", volubility

    if volubility > 1:
        argv1 = sys.argv[1]
        print "  sys.argv[%d] = %s" % (1, argv1) ,
    else :
        exit ("  you should input the IP address of openTSDB server like 10.0.0.1:4242")

    return argv1


if __name__== "__main__" :
    print "...starting..."
    url = ''
    url = helpmsg()
    if len(url) < 5:
        exit ("   you should input the IP address of openTSDB server \
        like 10.0.0.1:4242")
    else:
        url = 'http://' + url + '/api/put'
        print url
    otsdb_restful_put(url)
    time.sleep(0.1)
    print "\n ...ending..."
