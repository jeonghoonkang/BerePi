#-*- coding: utf-8 -*-
import simplejson as json
#api 호출
import httplib, urllib, urllib2
#URL 검색
import matplotlib.pyplot as plt
import matplotlib.legend as legend #그래프 설정
import json
#url의 json 파싱
import datetime
#x축의 시간 설정
import numpy as np


print 'url read'
print '24시간 값이 있는 uuid'
print "http://new.openbms.org/backend/api/data/Metadata__SourceName/Sutardja%20Dai%20Hall%20BACnet"
url="http://new.openbms.org/backend/api/data/Metadata__SourceName/Sutardja%20Dai%20Hall%20BACnet"
data = json.load(urllib2.urlopen(url))
                #url의 데이터 정보를 받아옴  json형식
data2 = json.dumps(data)
                #구분자를 " "나눔
data3 = json.loads(data2)
#구분자를u'항목'으로 분류
print 'url end'

note=[]
gradient=[]
time =[]
value=[]
t=0
data_min=0
data_max=0

for i in range(0,len(data3)):
    
    
    
                #print type (uuid)
                #데이터 타입 확인
    if data3==[] :
        #print('nodata or wrong input')
        n=0
    elif data3[i]["Readings"]=='' :
       # print('nodata or wrong input')
        n=0
    elif data3[i]["Readings"]==[]:
       # print('nodata or wrong input')
        n=0
    else :
        value=[0]
        uuid =data3[i]["uuid"]
        note.append(uuid)
        
        value.append(100.0)
        for j in range(0,len(data3[i]["Readings"])) :
            
            #print len(data3[i]["Readings"])
            #print 'url read'
            #url1="http://new.openbms.org/backend/api/tags/uuid/%s" % uuid
            #print 'url end'
            #tag_data = json.load(urllib2.urlopen(url1))
                    #url의 데이터 정보를 받아옴  json형식
            #tag_data2 = json.dumps(tag_data)
                    #구분자를 " "나눔
            #tag_data3 = json.loads(tag_data2)
                    #구분자를u'항목'으로 분류
            #Path = tag_data3[0]["Path"]
            
            #t=int(data3[i]["Readings"][j][0])/1000
            #tt=datetime.datetime.fromtimestamp(t)
            
            #time.append(tt)
            #print 1
            #print i , j
            v = float(data3[i]["Readings"][j][1])

            value.append(v)
            
            if v >= data_min :
                data_min = data_min

            else :
                data_min = v
                                #데이터의 최소 값 추출
            if v >= data_max :
                data_max = v

            else :
                data_max = data_max
                                #데이터의 최대 값 추출
                
            #print uuid,  tt,  v                   
            #print('%s\t%s\t%s\t\t\t%s/%s\n') %(i+1,tt,v,i+1,len(data3[0]["Readings"]))
            t= str(data3[i]["uuid"])
            #print uuid,  value
            if j == len(data3[i]["Readings"])-1 :
                gradient.append(value)
                #print gradient
                #print i+1           


print('그래프 그리는 중입니다')

cmaps = [('UCB_Metadata',  note )]


nrows = max(len(cmap_list) for cmap_category, cmap_list in cmaps)
#print gradient
#print len(note)

for cmap_category, cmap_list in cmaps:
    #print 'graph'
    fig, axes = plt.subplots(nrows=nrows)
    fig.subplots_adjust(top=0.95, bottom=0.01, left=0.2, right=0.99)
    axes[0].set_title(cmap_category + ' Monitoring', fontsize=14)
    n=0
    
    #print gradient[n]
    for ax, name in zip(axes, cmap_list):
        
        gradientt = np.vstack((gradient[n], gradient[n]))
        n+=1
        ax.imshow(gradientt, aspect='auto', cmap='Blues')
        pos = list(ax.get_position().bounds)
        x_text = pos[0] - 0.01
        y_text = pos[1] + pos[3]/2.
        fig.text(x_text, y_text, name, va='center', ha='right', fontsize=10)
        
    # Turn off *all* ticks & spines, not just the ones with colormaps.
    for ax in axes:
        ax.set_axis_off()
    print '현재 들어 오고 있는 uuid의 수 : %s개 입니다. 각 uuid당 데이터 값의 수 : %s개 입니다.' %(n,len(gradient[0]))


plt.show()
