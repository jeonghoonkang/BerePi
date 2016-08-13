# -*- coding: utf-8 -*-


from matplotlib.dates import HourLocator, MinuteLocator, DateFormatter, date2num
import MySQLdb
import datetime
import pylab
import time, sys, os



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

    if ( (nowDate.day - payCountDay) < 0 ) : # prev. month
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
    ## collect DB data from MySQL DB to row
    #print "[msg]......calling funciton... currentMonthValue()",
    #print currentMonthValue
    etypenodeid = str(nodeid)
    
    nowDate = datetime.datetime.today()

    if ( (nowDate.day - payCountDay) < 0 ) : # prev. month
      m2ago = nowDate.month - 2
      m1ago = nowDate.month - 1
    else: # same month
      m2ago = nowDate.month - 1
      m1ago = nowDate.month 

    findingDateM1ago = nowDate.replace(month=m1ago,day=payCountDay,hour=0,minute=0,second=0)
    findingDateM2ago = nowDate.replace(month=m2ago,day=payCountDay,hour=0,minute=0,second=0)

    queryDayM1ago = datetime.date(findingDateM1ago.year, findingDateM1ago.month, findingDateM1ago.day)
    queryDayM2ago = datetime.date(findingDateM2ago.year, findingDateM2ago.month, findingDateM2ago.day)

    print 
    print ' from ' + str(queryDayM2ago),
    print ' to ' + str(queryDayM1ago)

    ## Accumulated Watt Hour
    sql = "select * from ETYPE_HISTORY where nodeid=%s and \
           regdate >= '%s' order by regdate limit 1" \
           % (nodeid, queryDayM2ago)

    WattH = []

    ## excute Query 
    cursor.execute(sql)
    WattH = cursor.fetchone() 
    ## if Watth is lack of data, it means DB server does not have data
    ### should check DB schema in order to use exact order of WattH[x]
    preVal = WattH[5]
    print ' 2 Month ago Meter Valud : %d ' % preVal


    sql = "select * from ETYPE_HISTORY where nodeid=%s and \
           regdate >= '%s' order by regdate limit 1" \
           % (nodeid, queryDayM1ago)

    ## excute Query 
    cursor.execute(sql)
    WattH = cursor.fetchone() 
    curVal = WattH[5]
    
    #print ' 1 Month ago Meter Valud : %d ' % curVal

    preMonMeter = ((curVal-preVal)/1000.0)
    print ' Previous Month Usage : %f kWh ' % preMonMeter 

    return preMonMeter


def calcPay(meterVal):
    #print "[msg]......calling funciton... calcPay()",
    #print calcPay 
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

    #print 'debug = %d ' % payIndex
    korwon = 0
    onCalc = 0
    lastCalc = 0

    for loop in range(0, payIndex+1) :
      if loop is payIndex:
        ### last add  
        lastCalc = onCalc + payTable_base[loop] + ( payTable_multiplier[loop] * (meterVal%100) )
      else :
        onCalc += (payTable_multiplier[loop] * 100)

    korwon = lastCalc + (lastCalc*0.137)
    print ' Pay KOR_WON = %d ' % korwon
    print
    return korwon


    cursor.close()
    db.close()
    print " Closing DB sessions. all done successfully "
    print


result = [[], [], [], [], [], [], []]
dates = [[], [], [], [], [], [], []]
x = [[], [], [], [], [], [], []]
row, datetime_ = [], []

db = MySQLdb.connect("...", "keti", "keti123!@#", "PEAKSAVE")
cursor = db.cursor()

EtypeId = 911
payCountDay = 26

ret = "Meter ID = " + str(EtypeId)+",  "
ret = ret + "Pay check day is " + str(payCountDay) + " " + "<br>"

nodeid = EtypeId 

meterVal = lastMonthValue(nodeid)
ret = ret + " Previous month payment = " + str (calcPay(meterVal)) + " KOR WON" + "<br><br> "

meterVal = currentMonthValue(nodeid)
ret = ret + " This Month = <br> <font size=12> " + str (meterVal) + " kW" + "<br><br> "
ret = ret + str (calcPay(meterVal)) + " KOR WON <br>" + " </font><br> is this month payment until now<br> "  + "<br> "
ret = ret + str (datetime.datetime.today()) + "<br> "


