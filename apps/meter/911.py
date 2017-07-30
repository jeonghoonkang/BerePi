#!/usr/bin/python
# -*- coding: utf-8 -*-
# Author : Jeonghoonkang, github.com/jeonghoonkang 

from matplotlib.dates import HourLocator, MinuteLocator, DateFormatter, date2num
#import MySQLdb
import datetime
import pylab
import time, sys, os
#from datetime import timedelta

devel_dir = "/home/pi/devel"
tmp_dir = devel_dir+"/danalytics/thingsweb/weblib/recv"
sys.path.append(tmp_dir)

from lastvalue import *

day_delta = 0
tmp_delta = 0

def currentMonthValue(nodeid) :
    ## collect DB data from MySQL DB to row
    #print "[msg]......calling funciton... currentMonthValue()",
    #print currentMonthValue
    etypenodeid = str(nodeid)
    
    nowDate = datetime.datetime.today()
    #print str(nowDate)

    ### today - payD > 0 and == 0 
    ### same month : just today val - payD val and calculation
    ### today - payD < 0
    ### one month before, find previous month date 

    global day_delta
    day_delta = nowDate.day - payCountDay
    
    if ( day_delta < 0 ) : # prev. month
      td = datetime.timedelta(days=-31)
      findingPreDate = nowDate + td
    else: # same month
      findingPreDate = nowDate

    if (findingPreDate.day != payCountDay) :
      payDayStart = findingPreDate.replace(day=payCountDay,hour=0,minute=0,second=0)
      ### only supports copying datetime object. 
    else :
      payDayStart = findingPreDate.replace(hour=0,minute=0,second=0)

    queryDay = datetime.date(payDayStart.year, payDayStart.month, payDayStart.day)
    print 
    print ' from ' + str(queryDay) + ' to Today'


    ## Accumulated Watt Hour
    sql = "select * from ETYPE_HISTORY where nodeid=%s and \
           regdate >= '%s' order by regdate limit 1" \
           % (nodeid, queryDay)

    WattH = []

    ## excute Query 
    cursor.execute(sql)
    WattH = cursor.fetchone() 
    ### should check DB schema in order to use exact order of WattH[x]
    preVal = WattH[5]
    #print ' Previous Month Meter Valud : %d ' % preVal


    sql = "select * from ETYPE_HISTORY where nodeid=%s \
           order by code desc limit 1" \
           % (nodeid)


    ## excute Query 
    cursor.execute(sql)
    WattH = cursor.fetchone() 
    curVal = WattH[5]
    
    #print ' This Month Meter Valud : %d ' % curVal

    curMonMeter = ((curVal-preVal)/1000.0)
    print ' This Month on-going Usage : %f kWh ' % curMonMeter 

    return curMonMeter

def lastMonthValue(nodeid) :
    #print "[msg]......calling funciton... currentMonthValue()",
    etypenodeid = str(nodeid)
    
    nowDate = datetime.datetime.today()
    print nowDate
    nowTime = nowDate.strftime("%H:%M:%S")

    if ( (nowDate.day - payCountDay) < 0 ) : # prev. month
      m2ago = nowDate.month - 2
      m1ago = nowDate.month - 1
    else: # same month
      m2ago = nowDate.month - 1
      m1ago = nowDate.month 

    #datetime.datetime
    findingDateM1ago = nowDate.replace(month=m1ago,day=payCountDay,hour=0,minute=0,second=0)
    findingDateM2ago = nowDate.replace(month=m2ago,day=payCountDay,hour=0,minute=0,second=0)

    # convert to datetime.time
    queryDayM1ago = datetime.date(findingDateM1ago.year, findingDateM1ago.month, findingDateM1ago.day)
    queryDayM2ago = datetime.date(findingDateM2ago.year, findingDateM2ago.month, findingDateM2ago.day)
