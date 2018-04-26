#!/usr/bin/python
# Author : jeonghoonkang, https://github.com/jeonghoonkang
#-*- coding: utf-8 -*-

from __future__ import print_function
from subprocess import *
from types import *
import sys

def run_cmd(cmd):
    p = Popen(cmd, shell=True, stdout=PIPE)
    output = p.communicate()[0]
    return output

def hostname():
    cmd = "hostname"
    ret = run_cmd(cmd)
    return ret

def getip():
    cmd = "curl http://checkip.amazonaws.com"
    ip = run_cmd(cmd)
    return ip

def getiip():
    cmd="/sbin/ifconfig"
    iip = run_cmd(cmd)
    return iip

def checkifexist(fname):
    cmd='ls ' + fname
    print (run_cmd(cmd))

def writefile(_in, fn="ip.txt"):
    f = open(fn, 'w')
    f.write(_in)
    f.flush()
    f.close()
    return

if __name__ == '__main__':
    dirs = "./out"
    p_ip = getip()
    i_ip = getiip()
    info = i_ip + p_ip
    hostn = hostname()
    fname = '/home/tinyos/devel/BerePi/apps/tinyosGW/out/%s.txt' %hostn[:-1]

    writefile (info, fname)
    checkifexist(fname)

    cmd = "scp" + " %s " %fname + 'pi@dns.iptime.org:' + '/var/www/html/server/'
    ret = run_cmd(cmd)
    print (" ")
    print (ret)

# ssh-keygen
# cat ~/.ssh/id_rsa.pub | ssh -p xxxx pi@xxx.xxx.xxx 'cat >>
# .ssh/authorized_keys'
