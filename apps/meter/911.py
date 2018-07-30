#!/usr/bin/python
# -*- coding: utf-8 -*-

# Author : Jeonghoonkang, github.com/jeonghoonkang

from matplotlib.dates import HourLocator, MinuteLocator, DateFormatter, date2num
#import MySQLdb
import datetime
import pylab
import time, sys, os
import cgi
import cgitb

#from datetime import timedelta

devel_dir = "/home/pi/devel"
tmp_dir = devel_dir+"/danalytics/thingsweb/weblib/recv"
sys.path.append(tmp_dir)

from lastvalue import *

day_delta = 0
tmp_delta = 0

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
    queryToday = datetime.date(nowDate.year, nowDate.month, nowDate.day)

    _2month_before = str(queryDayM2ago)
    _2month_before = _2month_before.replace('-','/') + '-00:00:'

    _1month_before = str(queryDayM1ago)
    _1month_before = _1month_before.replace('-','/') + '-00:00:'

    print
    print 'from ' + _1month_before[:10],
    print ' to now ' + str(nowDate)[:16],
    print ', considering ' + _2month_before[:10]
    print

    _2month_before_30 = _2month_before

    _s2 = _2month_before+'00'
    _e2 = _2month_before+'30'
    _s1 = _1month_before+'00'
    _e1 = _1month_before+'30'

    _today_start = str(nowDate)
    _today_start = _today_start.replace('-','/')
    print _today_start
    _today_start = _today_start[:10]+'-00:00:00'
    print _today_start
    _today_end = str(nowDate)
    _today_end = _today_start.replace('-','/')
    _today_end = _today_end[:10]+'-00:01:00'

    tmp_val0 = get_value(dbip, metric, {'id':'911'}, _s2 , _e2)
    tmp_val1 = get_value(dbip, metric, {'id':'911'}, _s1, _e1)
    tmp_val2 = get_last_value(dbip, metric, {'id':'911'})
    #today 0:0:0
    tmp_val3 = get_value(dbip, metric, {'id':'911'}, _today_start, _today_end)

    if tmp_val0 == None:
        tmp_val0 = keepSearch(findingDateM2ago, _e2)

    if tmp_val1 == None :
        tmp_val1 = keepSearch(findingDateM1ago, _e1)

    if tmp_val2 == None :
        tmp_val2 = keepSearch(findingDateM1ago, _e2)

    print " check values"
    print tmp_val0, tmp_val1, tmp_val2, "\n"

    current_wattH = int(tmp_val2[0])-int(tmp_val1[0])
    lastmonth_wattH = int(tmp_val1[0])-int(tmp_val0[0])

    global day_delta
    day_delta = nowDate.day - payCountDay

    # calc, how many days are passed from previous pay_count_day
    # to do : add code for 26, same day, not 1 day passed yet
    if (day_delta > 0) :
        passed_day = day_delta
    else :
        passed_day = 30 + day_delta

    #print "delta", day_delta
    #print "passed day", passed_day
    #print "current wattH", current_wattH

    est_watt = (current_wattH/1000.0 * (30.0 / passed_day))

    print "오늘 사용량 : %d kWh" %( (tmp_val2 - tmp_val3)/1000 )
    print "많이쓴날 20kWh, 아주많이 쓴날 30kWh"

    print "current watt : %d kWh" %(current_wattH/1000.0)
    #calcPay(current_wattH/1000.0)

    print "expected watt on next month, day of 26, is %d kWh" %est_watt
    #print "Money %d Won" %calcPay(est_watt)
    #calcPay(est_watt)

    print
    print "previous Month watt : %d kWh" %(lastmonth_wattH/1000.0)
    #calcPay(lastmonth_wattH/1000.0)

    print
    print "Info.  30,000 won, 233 kWh"
    print "Info.  44,390 won, 300 kWh"
    print "Info.  65,760 won, 400 kWh"
    print "Info.  88,190 won, 450 kWh"
    print "Info. 104,140 won, 500 kWh"
    print "Info. 136,040 won, 600 kWh"
    print "Info. 199,850 won, 800 kWh"
    #calcPay(233.0)

    exit ("under develplemnt now")

    ## Accumulated Watt Hour

    ## excute Query
    ## if Watth is lack of data, it means DB server does not have data
    ### should check DB schema in order to use exact order of WattH[x]
    preVal = current_tot_etype[0]
    print ' 2 Month ago Meter Valud : %d ' % preVal

    #preMonMeter = ((curVal-preVal)/1000.0)
    #print ' Previous Month Usage : %f kWh ' % preMonMeter

    return preMonMeter

def keepSearch(st, et, limit=48 ) :
    cnt = limit
    for idx in range(limit-1, 0, -1) :
        cnt = idx - limit
        back = st + datetime.timedelta(days=cnt)
        qrs = back.strftime('%Y/%m/%d-%H:%M:%S')
        _r = get_value(dbip, metric, {'id':'911'}, qrs, et)
        if _r != None: return _r
    return None

def calcPay(meterVal):
    # print "[msg]......calling funciton... calcPay()",
    # print calcPay
	# test value
    # meterVal = 630
    payTable_level=['1L', '2L', '3L', '4L', '5L', '6L']
    payTable_base=[410, 910, 1600, 3850, 7300, 12940]
    payTable_multiplier=[60.7, 125.9, 187.9, 280.6, 417.7, 709.5]

    if (meterVal > 500.0):
      payIndex = 5
    elif (meterVal > 400.0):
      payIndex = 4
    elif (meterVal > 300.0):
      payIndex = 3
    elif (meterVal > 200.0):
      payIndex = 2
    elif (meterVal > 100.0):
      payIndex = 1
    else :
      payIndex = 0

    #print 'debug PAYINDEX = %d ' % payIndex
    korwon = 0
    onCalc = 0
    lastCalc = 0
    last_loop = 0
    if meterVal == None :  meterVal = 0
    last_loop = int(meterVal // 100) + 1
    #print last_loop

    # 1 step : calc meterVal 0 ~ 100
    if meterVal < 100.0 :
        lastCalc = payTable_base[0] + ( payTable_multiplier[0] * (meterVal) )

    # 2 step : calc meterVal 100 ~ 599, 2 < last_loop < 7
    elif (last_loop < 7) :
        for loop in range(0, payIndex) :
            onCalc += (payTable_multiplier[loop] * 100)
        lastCalc = onCalc + payTable_base[payIndex] + ( payTable_multiplier[payIndex] * (meterVal%100) )

    # 3 step : calc meterVal beyond 600, last_loop > 6
	# test value : 630 -> 241560, last_loop == 7
    elif (last_loop > 6) :
         for loop in range(0, 6) : # 0 ~ 5 payIndex
            onCalc += (payTable_multiplier[loop] * 100)
         for loop in range(6, last_loop-1) : # 6 ~ something payIndex
            onCalc += (payTable_multiplier[5] * 100)
         lastCalc = onCalc + payTable_base[5] + ( payTable_multiplier[5] * (meterVal%100) )

    #print onCalc
    #print lastCalc

    korwon = lastCalc + (lastCalc*0.137)
    print ' Pay KOR_WON = %d ' % korwon
    print
    return korwon


def closingTask():
    cursor.close()
    db.close()
    print " Closing DB sessions. all done successfully "
    print


if __name__== "__main__" :

    cgitb.enable()

    dbip="127.0.0.1:4242"
    #dbip="input your IP or URL"
    metric = 'rc01.t_power.WH'
    result = [[], [], [], [], [], [], []]
    dates = [[], [], [], [], [], [], []]
    x = [[], [], [], [], [], [], []]
    row, datetime_ = [], []
    # delete due to MySQL
    #db = MySQLdb.connect("125.7.128.51", "keti", "keti123!@#", "PEAKSAVE")
    #cursor = db.cursor()

    EtypeId = 911
    payCountDay = 25

    ret = "Meter ID = " + str(EtypeId)+",  "
    ret = ret + "Pay check day is " + str(payCountDay) + " " + "<br>"

    nodeid = EtypeId

    # important functions are here
    # (fun) lastMonthValue(nodeid)
    # (fun) calcPay(meterVal)
    # (fun) currentMonthValue(nodeid)

    # current_etype = get_last_value(dbip,'gyu_RC1_etype.current',{'nodeid':'911'})
    # current_tot_etype = get_last_value(dbip,'gyu_RC1_etype.t_current',{'nodeid':'911'})

    #print "<Content-Type: text/html;charset=utf-8>"
    #print '<font size="20">'

    meterVal = lastMonthValue(nodeid)
    ret = ret + " Previous month payment = " + str (calcPay(meterVal)) + " KOR WON" + "<br><br> "

    #meterVal = currentMonthValue(nodeid)
    ret = ret + " This Month = <br> <font size=12> " + str (meterVal) + " kW" + "<br><br> "
    ret = ret + str (calcPay(meterVal)) + " KOR WON <br>" + " </font><br> is this month payment until now<br> "  + "<br> "
    ret = ret + str (datetime.datetime.today()) + "<br> "

#    print ret

    #closingTask()
