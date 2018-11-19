# -*- coding: utf-8 -*-
# Author : jeonghoonkang , https://github.com/jeonghoonkang

import time
import datetime
import os
import requests
import json
import argparse
import calendar
import urllib2
import socket
from operator import itemgetter, attrgetter
import ast
import sys
sys.path.insert(0, '../')

HOST = '127.0.0.1'
PORT = 4242
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((HOST, PORT))

def parse_args():

    story = 'OpenTSDB needs many arguments URL, start time, end time, port '
    usg = '\n python tsdb_read.py  -url x.x.x.x \
        -port 4242 -start 2016110100 -end 2016110222 \
        -rdm metric_name, -wm write_metric_name --help for more info'

    parser=argparse.ArgumentParser(description=story,
        usage=usg,
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument("-url",    default='127.0.0.1',
        help="URL input, or run fails")
    parser.add_argument("-start",  default='2016070100',
        help="start time input, like 2016110100")
    parser.add_argument("-end",    default='2017070100',
        help="end time input, like 2016110223")
    parser.add_argument("-port",   default=4242,
        help="port input, like 4242")
    parser.add_argument("-recent", default=None,
        help="Time input for recent value")
    parser.add_argument("-rdm", default=None,
        help="metric ")
    parser.add_argument("-val", default=None,
        help="value which will be inserted to OpenTSDB")
    parser.add_argument("-wtm", default='___d_tag_test_load_rate_6',
        help="write-metric ")
    args = parser.parse_args()

    #check args if valid
    url = args.url
    _ht = 'http://'
    if ( url[:7] != _ht ) : url = _ht + url
    port = args.port
    if  port == 80 : port = ''
    else : port = ":"+ str(port)
    url = url + port +'/api/query?'

    start = args.start
    if start != None : start = args.start
    end = args.end
    if end != None : end = args.end

    recent = args.port
    if recent != None : recent = args.recent

    m = args.rdm
    if m == None : print("... this time will not use READ function")

    wm = args.wtm
    if m == None and wm == None :
        print usg
        exit("... I can not do anything without metric")

    return url, port, start, end, recent, m, wm, args.val

def sockWriteTSD(__wmetric, __utime, __value, __tags = None):

    if __tags == None: __tags = 'duptest=true'
    _buf = "put %s %s %s %s\n" %( __wmetric, __utime, __value, __tags)
    ret = sock.sendall(_buf)
    pout = "  .... writing to TSDB, return(%s), cmd(%s) \r \r" %(ret, _buf)
    sys.stdout.write(pout)
    sys.stdout.flush()

    return

if __name__ == "__main__":
    u, p, stime, etime, recent, metric, write_metric, val = parse_args()

    #insert_load_rate(u, metric, write_metric, inlist, maxdict, stime, etime)
    #insertValue_periodically(u, write_metric, val, stime, etime, 60)
    #print getdict
    #print " Help message"

    #cpmetric(u, metric, stime, etime, write_metric )
    #ret = countall(u, metric, stime, etime, inlist)
