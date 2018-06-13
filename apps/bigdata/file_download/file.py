#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import numpy as np
import json
import time
import datetime
import os.path
import sys


def inputfile_chck(fname):
    if os.path.isfile('./'+_internet_file_name_):
        with open("./"+_internet_file_name_) as data_file:
            data = json.load(data_file)
            if 0 : print data[0].keys()
            print " previous old downlaod file exists... "
    else:
        print "There is no file on the disk, try to download from internet"
        target_file = 'https://raw.githubusercontent.com/jeonghoonkang/BerePi'
        target_file += '/master/apps/bigdata/file/2014_06_01_gps_sangic_kwangic.json'
        print target_file
        _response = urllib2.urlopen(target_file)
        _of = open(_internet_file_name_, 'wb')
        meta = _response.info()
        if 0 : print meta
        _fsize = int (meta.getheaders("Content-Length")[0])
        _blk = (1024*8)
        _cursor_ = 0
        while True:
            buff = _response.read(_blk)
            if not buff: break
            _cursor_ += len(buff)
            _of.write(buff)
            _pout = " download progress, %s " %(_internet_file_name_)
            _pout += " %3.2f %%" %(100.0*_cursor_/_fsize)
            _pout += "       %s / %s " %(_cursor_, _fsize)
            _pout += "\r"
            sys.stdout.write(_pout)
            sys.stdout.flush()
        _of.close()
        with open("./"+_internet_file_name_) as data_file:
            data = json.load(data_file)
        if 0: print data

    return data

if __name__ == "__main__":

    _internet_file_name_ = "_input_json.json"

    try :
        with open('./2014_06_01_filtered_data.json') as data_file:
            data = json.load(data_file)
    except :
        data = inputfile_chck(_internet_file_name_)
        
        
        
    
