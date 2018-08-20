# -*- coding: utf-8 -*-
#Author : jeonghoonkang, https://github.com/jeonghoonkang

devel_dir="/home/pi/devel"
tmp_dir=devel_dir+"/BerePi/apps"

from types import *
import sys
import time
import datetime
import requests
import json
import subprocess
import ketidatetime
import time


'''  example : url = "http://10.0.0.43:4242/api/put
     warning : we have to 50 JSON pack to put in OpenTSDB, on first stage.
               if you add more, you shoud test amount of TX packets '''

def otsdb_restful_put(url, metric=None, ts=None, val=None, tags=None, iter_n=1 ):

    if  tags == None :
        sname = "kang.tinyos.test.000"
        sensor = "keti.put.test"
        tags = {
            "sensor" : "keti.put_test",
    	    "name" : sname
        } #tags should be less than 9, 8 is alright, 9 returns http error

    mname = metric
    if metric == None :
        mname = "__keti.tinyos.test.0001__"

    print ts
    if ts == None or ts == 'now' : uts = int(time.time())
    else :
        ts = ketidatetime._check_time_len(ts)
        print ts
        uts = ketidatetime.datetime2ts(ts)
        print uts

    print "  metric name = ", mname

    print tags
    tags = eval(tags)
    print type(tags)


    ''' if you want to add iteration, use iter_n valiable '''
    for i in range(0,iter_n):
        if val == None : exit('can not make forward val = None')
        data = {
            "metric": mname, #alphabet and number . _ /
            "timestamp": int(uts),
            "value": val, #integer
            "tags": tags
        }

        print data

        ''' if you want to check inserted POINT on TSDB server,
            use below URL to check, you should modify URL PORT to proper IP address
            http://URL:PORT/api/query?start=2018/06/25-00:00:00&end=2018/06/26-00:00:00&m=none:keti.tinyos.packet.test
        '''

        try :
            #s = requests.Session()
            ret = requests.post(url, data=json.dumps(data))
            print ret.content
            print "\n return is ", ret


            outstring = "\n  now trying to put below data to TSDB, url %s " %(url)
            outstring += str(data)
            outstring += "\n try %d / %d " % (i, iter_n-1)
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
    print   "  *** TEST OpenTSDB put                      *** "
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

import argparse
def parse_args():

    story = 'OpenTSDB needs many arguments URL, start time, end time, port '
    usg = '\n python tsdb_read.py  -url x.x.x.x \
        -port 4242 -start 2016110100 -end 2016110222 \
        -rdm metric_name, -wm write_metric_name -tags="{id:911}" --help for more info'

    parser=argparse.ArgumentParser(description=story,
        usage=usg,
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument("-url",    default="127.0.0.1",
        help="URL input, or run fails")
    parser.add_argument("-start",  default='2016070100',
        help="start time input, like 2016110100")
    parser.add_argument("-port",   default=4242,
        help="port input, like 4242")
    parser.add_argument("-val", default=802,
        help="value which will be inserted to OpenTSDB")
    parser.add_argument("-wtm", default='__keti_test__',
        help="write-metric ")
    parser.add_argument("-tags", default="{'sensor':'_test_sensor_', 'desc':'_test_'}",
        help="tags ")
    args = parser.parse_args()

    #check args if valid
    url = args.url
    _ht = 'http://'
    if ( url[:7] != _ht ) : url = _ht + url
    port = args.port
    if  port == 80 : port = ''
    else : port = ":"+ str(port)
    url = url + port +'/api/put'


    wm = args.wtm
    if wm == None :
        print usg
        exit("... I can not do anything without metric")

    return url, wm, args.start, args.val, args.tags

def put_tsdb(url, write_metric, time, val, tags):
    if url.find('http') == -1 :
        url = 'http://' + url + ':4242'
    otsdb_restful_put(url, write_metric, time, val, tags)
    #python put_test.py -url 192.168.0.200 -start 2018081800 -val 21766000 -wtm rc01.t_power.WH -tags "{'id':'911'}"

def put_now_tsdb(url, write_metric, time, val, tags):
    if url.find('http') == -1 :
        url = 'http://' + url + ':4242'
    otsdb_restful_put(url, write_metric, 'now', val, tags)

if __name__== "__main__" :
    print "...starting..."

    args = parse_args()
    print args
    otsdb_restful_put(args[0], args[1], args[2], args[3], args[4])

    time.sleep(0.1)
    print "\n ...ending..."
