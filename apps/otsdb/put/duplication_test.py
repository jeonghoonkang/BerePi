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

HOST = '125.140.110.217'
PORT = 4242
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((HOST, PORT))

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
    
    ret = countall(u, metric, stime, etime, inlist) 
  
  
