#-*- coding: utf-8 -*-

import pylab, MySQLdb, datetime
from GSBC_nodeid import *

def init_():
    global result, dates, x, row, datetime_, value, PSR, NPSR, minutessum
    result, dates = [], [[]]
    value, x, row, datetime_ = [], [[]], [], []
    PSR, NPSR=[], []
    minutessum=datetime.timedelta(seconds=0)
def DTsp_() :
    global datetime1, datetime2
    datetime1 = datetime.datetime.strptime(datetimestand+ " 00:00:00", '%Y-%m-%d %H:%M:%S')
    td = datetime.timedelta(days=intervalday)
    datetime2 = td + datetime1
    print str(datetime1) + ' ' + str(datetime2)

def typevalue_(datetime1, datetime2, node) :
    global DBtable
    node = str(node)
    if cmap_category[0]=='S' :
        DBtable='SPLUG'
    elif cmap_category[0]=='C' :
        DBtable='CO2'
    if node==cmap_list[-1] :
        DBtable='BASE'
    sql = "select regdate, nodeid from %s_HISTORY where nodeid=%s and '%s' <= regdate and  regdate < '%s'  order by regdate asc" \
        % (DBtable, node, datetime1, datetime2)
    cursor.execute(sql)
    row.append(list(cursor.fetchall()))  # CO2
    row[0].append([datetime2,node])
    return row
def data_():
    global number
    number=0
    datetime_start=datetime1
    datetime_end=datetime_start+datetime.timedelta(minutes=5)
    result.append(0)
    for date in row[number] :
        if date[0]>=datetime_end :        
            for count_minutes in range(1,288*intervalday) :
                result.append(0)
                datetime_start= datetime_start+datetime.timedelta(minutes=5)
                datetime_end= datetime_start+datetime.timedelta(minutes=5)
                if date[0]<=datetime_end :
                    break
        elif date[0]>= datetime_start and date[0]<datetime_end :
            result.append(0.2)
            datetime_start= datetime_start+datetime.timedelta(minutes=5)
            datetime_end= datetime_start+datetime.timedelta(minutes=5)
    value.append(result)

def plot_color_gradients(cmap_category, cmap_list):
    global ncolums, number, DBtable
    axes[0][ncolums].set_title(cmap_category + ' Monitoring', fontsize=14)
    for ax, name in zip(axes, cmap_list):
        gradient_vstack = pylab.vstack((value[number], value[number]))
        number+=1
        ax[ncolums].imshow(gradient_vstack, aspect='auto', cmap='Blues')
        pos = list(ax[ncolums].get_position().bounds)
        x_text = pos[0] - 0.01
        y_text = pos[1] + pos[3]/2.
        fig.text(x_text, y_text, name, va='center', ha='right', fontsize=10)
   
        # Turn off *all* ticks & spines, not just the ones with colormaps.
        for ax in axes:
            ax[ncolums].set_axis_off()
    ncolums=ncolums+1
    
db = MySQLdb.connect("114.207.113.78", "keti11", "keti0012!@", "GSBC_2014_1")
cursor = db.cursor()
intervalday=3 #show a few days on graph
DTmonth= "2014-2-" #month
DTdaystart=13 #start day
DTdayend=13 #end day
cmaps = 14 #raw_input("층수를 입력하세요. 1~14(5,6층 제외)")
cmaps = nodeid(cmaps)

ncolums=0
for day in range(DTdaystart, DTdayend+1) :
    nrows = max(len(cmap_list) for cmap_category, cmap_list in cmaps )
    fig, axes = pylab.subplots(nrows=nrows, ncols=len(cmaps) )
    fig.subplots_adjust(top=0.9, bottom=0.1, left=0.1, right=0.95, hspace=0.4)
    init_()
    for cmap_category, cmap_list in cmaps:
        datetimestand = DTmonth + str(day) # select the standard datetime
        DTsp_()
        for node in cmap_list : 
            row = typevalue_(datetime1, datetime2, node)
            data_()
            result,row=[],[]
        plot_color_gradients(cmap_category, cmap_list)
        value=[]
    pylab.show()
    