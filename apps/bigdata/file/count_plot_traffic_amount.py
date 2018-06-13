#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import json
from pprint import pprint
import time
import datetime
import matplotlib.pyplot as plt

def epochTOdatetimeStr(_timestamp):

    return datetime.datetime.fromtimestamp(_timestamp).strftime('%Y-%m-%d %H:%M:%S')

with open('./2014_06_01_filtered_data.json') as data_file:
    data = json.load(data_file)

keys = data[0]["timestamp_count"].keys()
keys = map(int, keys)
keys.sort()

values = []
times=[]

for k in keys:
    times.append(epochTOdatetimeStr(k))
    values.append(data[0]["timestamp_count"][str(k)])

#print times
#print values

plt.plot(times, values)
plt.xticks([])
plt.show()