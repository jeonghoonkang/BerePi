#-*- coding: utf-8 -*-
#!/usr/bin/python
# Author : jeonghoonkang, https://github.com/jeonghoonkang

from __future__ import print_function
from subprocess import *
from types import *

def run_cmd(cmd):
    p = Popen(cmd, shell=True, stdout=PIPE)
    output = p.communicate()[0]
    return output

def getip():
    cmd = "curl http://checkip.amazonaws.com"
    ip = run_cmd(cmd)
    return ip

if __name__ == '__main__':
    p_ip = getip()
    i_ip = getiip()
    info = p_ip + i_ip
    fname = '/home/USER/my_deamon/output/ip.html'
    writeFile (info, fname )
    cmd = "scp" + " %s" %fname + " pi@AAA.iptime.org:" + "/var/www/html/server/" + fname[-7:]

    cmd = "scp" + " ip.html" + " pi@iptime.org:" + "/var/www/html/ip.html" 
    print (cmd)
    print (run_cmd(cmd))
