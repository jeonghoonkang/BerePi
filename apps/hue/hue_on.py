#!/usr/bin/python
# -*- coding: UTF-8 -*-# enable debugging

import cgitb
cgitb.enable()    
import os

print "Content-Type:text/html;charset=utf-8"
print 

print __file__
print

#os.system('ls -l')

cmd00 ="curl -X PUT -H 'Content-Type: application/json'"
cmd01 =" -d '{" + '"on":true}' + "'" 
cmd02 =" 'http://192.168.0.*/api/RRIewjWhR0NZOqs0E7IvL9bocCxq5/lights/4/state'"

cmd = cmd00 + cmd01 + cmd02
print cmd 

os.system(cmd)
# 
