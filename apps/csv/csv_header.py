# -*- coding: utf-8 -*-
#Author : https://github.com/jeonghoonkang

import text as txt

line_num = 0

#print (text.first)
#exit(1)

firstlist = txt.first.split(",")   
secondlist = txt.second.split(",")   

print ("length of first :", len(firstlist))
print ("length of second :", len(secondlist))

if len(firstlist) == len(secondlist) :
    range_end = len(firstlist)

for idx in range(0,range_end) :
    print (firstlist[idx], secondlist[idx])

for idx in range(0,range_end) :
    line_num += 1
    print (line_num, firstlist[idx], "<##>", secondlist[idx])

if __name__== "__main__" :
    None

'''
for item in firstlist:
    print (item)

for item in secondlist:
    line_num += 1
    print (line_num, item)
'''