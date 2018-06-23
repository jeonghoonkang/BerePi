# _*_ coding: utf-8 _*_
# Author: https://github.com/sidsid6
# Author: https://github.com/jeonghoonkang

import folium
import numpy as np
import pandas as pd
import base64
import matplotlib.pyplot as plt
import json
import vincent
import datetime
import calendar
import time
import json
from pprint import pprint
import os
import matplotlib.dates as md
from matplotlib import colors as mcolors

sangil_gwangju_lat_limit=[37.451485, 37.546070]
sangil_gwangju_lon_limit=[127.180766, 127.265925]
hanam_jonam_lat_limit=[37.371774, 37.526683]
hanam_jonam_lon_limit=[126.893716, 127.194184]
yangjae_giheung_lat_limit=[37.220438, 37.461934]
yangjae_giheung_lon_limit=[127.041516, 127.099883]

def filter(_Lat, _Lon):
    filter_car_index = []

    for i in range(0, len(_Lat)):
        dat_len = len(_Lat[i])

        lat_start = _Lat[i][0]
        lat_end = _Lat[i][dat_len-1]
        lon_start = _Lon[i][0]
        lon_end = _Lon[i][dat_len-1]
        if lat_start >= sangil_gwangju_lat_limit[1] and lon_start <= sangil_gwangju_lon_limit[0] and lat_end <= sangil_gwangju_lat_limit[0] and lon_end >= sangil_gwangju_lon_limit[1]:
            filter_car_index.append(i)
        elif lat_end >= sangil_gwangju_lat_limit[1] and lon_end <= sangil_gwangju_lon_limit[0] and lat_start <= sangil_gwangju_lat_limit[0] and lon_start >= sangil_gwangju_lon_limit[1]:
            filter_car_index.append(i)

    return  filter_car_index


def plot_on_map(data, _index):

    resolution, width, height = 75, 7, 3
    lat, lon = (sangil_gwangju_lat_limit[0]/2 + sangil_gwangju_lat_limit[1]/2 ,
        sangil_gwangju_lon_limit[0]/2 + sangil_gwangju_lon_limit[1]/2)

    map = folium.Map(location=[lat, lon], zoom_start=10)
    Color = mcolors.CSS4_COLORS.values()
    countcar = 0

    for i in _index:
        countcar += 1
        print str(data[2][i])+'번 차량 지도에 그리는 중....'
        for j in range(0, len(data[0][i])):

            if j == 0:
                folium.Marker(location=[float(data[0][i][j]), float(data[1][i][j])],
                    icon=folium.Icon(color='red'),
                    popup=data[2][i]+'start').add_to(map)
            elif j == len(data[0][i]) - 1:
                folium.Marker(location=[float(data[0][i][j]), float(data[1][i][j])],
                    icon=folium.Icon(color='blue'),popup=data[2][i]+'end').add_to(map)

            folium.CircleMarker(location=[float(data[0][i][j]), float(data[1][i][j])],
                radius=20, line_color=Color[countcar],fill_color=Color[countcar],
                fill_opacity=0.1)

        folium.CircleMarker(location=[sangil_gwangju_lat_limit[1], sangil_gwangju_lon_limit[0]],
            radius=100, line_color='black',
            fill_color='black', fill_opacity=1)

        folium.CircleMarker(location=[sangil_gwangju_lat_limit[0], sangil_gwangju_lon_limit[1]], radius=100,
                          line_color='black', fill_color='black', fill_opacity=1)

    map.save('result.html')
    print "총 지나간 차량 : %.3s 대" % countcar

def openjson(_date):
    _Lat=[]
    _Lon=[]
    _Carid=[]

    if os.path.isfile(_date+'.json')==False:
        print "파일이 없습니다."
        pass
    else:
        with open(_date+'.json') as data_file:
            #input_data = data_file.read()
            #data = json.(input_data, indent=4)
            data = json.load(data_file)

        for i in range(0, len(data[0]['data'])):
            carnum = data[0]['data'][i]['carid']
            lat=[]
            lon=[]
            for j in range(0, len(data[0]['data'][i]['gps'])):
                lat.append(data[0]['data'][i]['gps'][j][1][0])
                lon.append(data[0]['data'][i]['gps'][j][1][1])
            _Lat.append(lat)
            _Lon.append(lon)
            _Carid.append(carnum)

        filtered_car_index=filter(_Lat, _Lon)
        plot_on_map([_Lat, _Lon, _Carid], filtered_car_index)

if __name__ == '__main__':

    st=datetime.datetime.now()
    data=openjson('20140601_sg')
    print("\n [Total] Working time: %.19s ~ %.19s" % (st, datetime.datetime.now()))
