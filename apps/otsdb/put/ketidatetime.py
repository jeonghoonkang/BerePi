# -*- coding: utf-8 -*-
# Author : jeonghoonkang, https://github.com/jeonghoonkang

from __future__ import print_function
import datetime
import time
import os
import sys

g_debug_on = 1
g_debug_off = 0

def _check_time_len( time ):

    if g_debug_off : print ( " ### warning, using %s which is under development " %__file__ )
    _debug_print = 1
    _ret_time = time
    print (time)
    _year = time[:4]


    _year_int = int(_year)
    assert isinstance(_year_int, int)
    if _year_int < int(1900) or _year_int > int(2100) :
        exit(" Error @ %s : please check time string, out of 1900 and 2100 " %__file__, _year_int)

    _year_month = time[4:6]

    if _year_month != "/":
        if g_debug_off : print (_year_month, 'It should be / ... changing... ')
        tmp = time[:10].replace('-','/')
        _ret_time = tmp + time[10:]
        #print (time)

    _month = time[4:6]
    _month = int(_month)
    assert isinstance(_month, int)
    if int(_month) > 12:
        print (_month)
        exit(" Error @ %s : please check time string " %__file__)

    _month_day = time[6:8]

    _day = time[6:8]
    if len(time) < 14:
        #_ret_time = _ret_time[:8] + '-' + time[8:]
        _ret_time = time[0:8] + '-00:00:00'

    if (_ret_time[:10].find('/') == -1):
        print (' / is missing')
        #_tmp_list = [_ret_time[:4], '/', _ret_time[4:-1]]
        _ret_time = _ret_time[:4] + '/' + _ret_time[4:]
        _ret_time = _ret_time[:7] + '/' + _ret_time[7:]
        print (_ret_time)
        #print (time)

    if g_debug_off :
        print (" debug_option ", _year, _year_month, _month, _month_day, _day )
        print (" changed to ", _ret_time)

    #exit(" Error @ %s : please check time string" %__file__)

    return _ret_time

def validdate(time):
    return _check_time_len(time)

def daydelta(_date_on, _date_off, dys=None, hrs=None, mins=None):

    _on    = str2datetime(_date_on)
    _off   = str2datetime(_date_off)
    if dys != None : _delta = _on + datetime.timedelta(days = 1)
    elif hrs !=None : _delta = _on + datetime.timedelta(hours = 1)
    elif mins !=None : _delta = _on + datetime.timedelta(minutes = 20)
    if _delta == _off :
        return None
    else :
        return datetime2str(_delta)

def strday_delta(_s, _h_scale):
    _dt  = str2datetime(_s)
    if _h_scale == 24 : _dt += datetime.timedelta(days = 1)
    elif _h_scale == 24 : _dt += datetime.timedelta(hours = 1)
    elif _h_scale == 0.1 : _dt += datetime.timedelta(minutes = 20)
    _str = datetime2str(_dt)
    if g_debug_off :
        print (_str)
        iin = raw_input("go on? otherwise press [n]")
        if iin == 'n' : exit()
    return _str

def ts2datetime(ts_str):
    return datetime.datetime.fromtimestamp(int(ts_str)).strftime('%Y/%m/%d-%H:%M:%S')

def datetime2ts(dt_str):
    dt = datetime.datetime.strptime(dt_str, "%Y/%m/%d-%H:%M:%S")
    return time.mktime(dt.timetuple())

def dtstr2ts(dt_str):
    _time_string = _check_time_len(dt_str)
    dt = datetime.datetime.strptime(_time_string, "%Y/%m/%d-%H:%M:%S")
    return time.mktime(dt.timetuple())

def ts2str(ts):
    return str(int(ts))

def str2datetime(dt_str):
    return datetime.datetime.strptime(dt_str, "%Y/%m/%d-%H:%M:%S")

def datetime2str(dt):
    return dt.strftime('%Y/%m/%d-%H:%M:%S')

def add_time(dt_str, days=0, hours=0, minutes=0, seconds=0):
    return datetime2str(str2datetime(dt_str) + datetime.timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds))

def is_past(dt_str1, dt_str2):
    return datetime2ts(dt_str1) < datetime2ts(dt_str2)

def is_weekend(dt_str):
    if self.str2datetime(dt_str).weekday() >= 5: return '1'
    else: return '0'
