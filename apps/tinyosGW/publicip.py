#-*- coding: utf-8 -*-
#!/usr/bin/python
# Author : jeonghoonkang, https://github.com/jeonghoonkang

from __future__ import print_function
from subprocess import *
from types import *
import sys

def run_cmd(cmd):
    p = Popen(cmd, shell=True, stdout=PIPE)
    output = p.communicate()[0]
    return output

def getip():
    cmd = "curl http://checkip.amazonaws.com"
    ip = run_cmd(cmd)
    return ip

def getiip():
    cmd = "/sbin/ifconfig"
    iip = run_cmd(cmd)
    return iip

def writeFile(_in, fn = 'ip.txt'):
    f = open(fn, 'w')
    f.write(_in)
    f.flush()
    f.close()
    return

if __name__ == '__main__':
    p_ip = getip()
    i_ip = getiip()
    info = i_ip + p_ip 
    fname = '/home/tinyos/my_daemon/output/2T_.txt'

    writeFile (info, fname)
    
    cmd = "scp" + " %s" %fname + " pi@.iptime.org:" + "/var/www/html/server/" 
    ret = run_cmd(cmd)
    print (" ")
    print (ret)

