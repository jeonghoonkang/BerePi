# -*- coding: utf-8 -*-
#Author : https://github.com/jeonghoonkang


import text as txt
import pandas as pd


if __name__== "__main__" :

    line_num = 0
    buf = []
    #print (text.first)
    #exit(1)

    firstlist = txt.first.split(",")   
    secondlist = txt.second.split(",")   

    print ("length of first :", len(firstlist))
    print ("length of second :", len(secondlist))

    if len(firstlist) == len(secondlist) :
        range_end = len(firstlist)

    sub_buf=[]
    for idx in range(0,range_end) :
        line_num += 1
        print (line_num, firstlist[idx], "<##>", secondlist[idx])
#       buf.append(line_num)
        sub_buf.append(firstlist[idx])
        sub_buf.append(secondlist[idx])
        buf.append(sub_buf)
        sub_buf=[]
    
    print (buf)

    #exit(1)
    df = pd.DataFrame(buf,columns=["first","second"])
    df.to_csv("output.csv", header=None, index=None)       
    #''.join(str_list) 


'''
for item in firstlist:
    print (item)

for item in secondlist:
    line_num += 1
    print (line_num, item)

for idx in range(0,range_end) :
    print (firstlist[idx], secondlist[idx])
'''

#ref: https://velog.io/@dmstj907/Python%EC%9E%90%EB%8F%99%ED%99%94%EC%B2%98%EB%A6%AC-CSV%ED%8C%8C%EC%9D%BC-%EC%9D%BD%EA%B3%A0%EC%93%B0%EA%B8%B0