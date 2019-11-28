# -*- coding: utf-8 -*-
# Author : jeonghoonkang , https://github.com/jeonghoonkang

import time
import datetime
#import cx_Oracle
import os
import sys
import requests
import json
import time, datetime
import numpy as np

import _mds_id
import useTSDB
import socket
import csv
url = "http://125.140.110.217:4242/api/query?"
#url = "http://49.254.13.34:4242/api/put"
response ={}

HOST = '125.140.110.217'
PORT = 4242
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((HOST, PORT))

#openTSDB 리턴 예시
#{'metric': 'rc03_simple_data_led', 'aggregateTags': [], 'dps': {'1467301500': 0.9279999732971191, '1467298800': 0.07500000298023224, '1467299700': 0.8870000243186951, '1467302400': 0.9399999976158142, '1467300600': 0.9010000228881836}, 'tags': {'holiday': '0', 'mds_id': '00-250068136', 'led_inverter': 'led'}}
# metric, dps, tags


# main function
if __name__ == "__main__":

    sttime = "2016050100"
    entime = "2017050100"
    _unixtime = 1462028400
    _data_dict = {}
    __url = url
    __st = sttime
    __et = entime

    tsdbclass = useTSDB.u_ee_tsdb(__url, __st, __et)
    tsdbclass.set_metric('rc03_simple_data_led_v2')


    tagdata = ['aa','aa','aa','aa']
    ids = _mds_id.led_list
    toendpoint = len(ids)
    l = 0
    count = 0
    _dict_list = []
    for i in range (toendpoint):

        mds_id = ids[i]
        _tag = {'mds_id': str(mds_id)}

        ret_dict = tsdbclass.readTSD(_tag)
        if ret_dict == None: continue

        for __t, __v in ret_dict['dps'].items() :
            l = _unixtime - 1462028400
            if l <100000:
                _data_dict[_unixtime] = __v
                _unixtime +=1
                print l
            else:
                break
            #__t = 시간 __v = dps값? 측정값?

        if l < 100000:
            continue

        if count <= 10:
            _dict_list.append(_data_dict.copy())
            count += 1
            _unixtime -= 100000
            _data_dict.clear()
            if count == 10:
                break

    with open('_data_dict.csv', 'wb') as csv_file:
        writer = csv.writer(csv_file)

        __l = len(_dict_list)
        for key in _dict_list[0].iterkeys():
            writer.writerow([key]+ [(_dict_list[d])[key] for d in range(__l)])
        print i


    sock.close()
    print (" \n ... Finishing copying ... ")
