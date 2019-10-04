#!/usr/bin/env python
#-*- coding: utf-8 -*-
# Author : jeonghoonkang, https://github.com/jeonghoonkang

## 필독
'''
   ./out 디렉토리 생성해야 합니다
   ./out 권한은 sudo chgrp www-data out 으로 그룹 허가 추가
   sudo chmod 775 out
   '''

from __future__ import print_function
import cgi
import cgitb

from subprocess import *
from types import *
import platform
import sys
import os
import datetime

def run_cmd(cmd):
    p = Popen(cmd, shell=True, stdout=PIPE)
    output = p.communicate()[0]
    return output

def hostname():
    cmd = "hostname"
    ret = run_cmd(cmd)
    return ret

def get_df():
    cmd = "df -h"
    ret = run_cmd(cmd)
    return ret

def get_cron():
    cmd = 'for user in $(grep /bin/bash /etc/passwd | cut -f1 -d:); do crontab -u $user -l; done'
    ret = run_cmd(cmd)
    return ret

def get_file_count():
    cmd = "ls /var/www/html/cam/motion | wc -l"
    ret = run_cmd(cmd)

    cmd = "ls /var/www/html/cam/motion | grep avi | wc -l"
    val = run_cmd(cmd)
    ret = " Total -> " + ret
    ret = ret + " AVI -> " + val

    return ret

def getip():
    cmd = "curl http://checkip.amazonaws.com"
    ip = run_cmd(cmd)
    print ('[get-public-ip]', ip)
    return ip

def getiip():

    cmd="/sbin/ifconfig"
    _os_type = platform.system()
    _os_ver = os.uname()

    if (_os_ver[0] == 'Linux') :
        if (_os_ver[-1] == 'x86_64') :
            _os_type = 'Linux'
            cmd = "ifconfig"

    print ('os-type', _os_type)
    if _os_type.find('Cygwin') > 0:
        cmd = "ipconfig"
    iip = run_cmd(cmd)
    print (iip)
    return iip, _os_type

def get_ostype():
    _os_type = platform.system()
    #_os_machine = platform.machine()
    _os_ver = os.uname()
    #print (_os_ver)
    #출력예
    #('Linux', 'gate', '4.1.19+', '#858 Tue Mar 15 15:52:03 GMT 2016','armv6l')

    if (_os_ver[0] == 'Linux') :
        if (_os_ver[-1] == 'x86_64') :
            _os_type = 'Linux'
        if (_os_ver[-1] == 'armv6l') :
            _os_type = 'Rasbian'

    return _os_type

def checkifexist(fname):
    cmd='ls ' + fname
    print (run_cmd(cmd))

def writefile(_in, fn="ip.txt"):
    f = open(fn, 'w')
    f.write(_in)
    f.flush()
    f.close()
    return

def args_proc():

    msg = "usage : python %s {server_IP_ADD} {server_PORT} {server_id} {passwd_for_server}" %__file__
    msg += " => user should input arguments {} "
    print (msg, '\n')

    if len(sys.argv) < 2:
        exit("[bye] you need to input args, ip / port / id")

    arg1 = sys.argv[1]
    arg2 = sys.argv[2]
    arg3 = sys.argv[3]
    arg4 = sys.argv[4]

    ip   = arg1
    port = arg2
    id   = arg3
    passwd = arg4

    print ("... start running, inputs are ", ip, port, id, passwd)

    return ip, port, id, passwd

if __name__ == '__main__':

    cgitb.enable()
    print ("Content-type: text\n")
    #print ("Content-type: text/html\n")

    os_type = get_ostype()
    info = get_cron()
    #info = info + 'file count = ' + get_file_count()
    #print (os_type)

    hostn = hostname()

    if os_type == 'Rasbian': name = 'pi'
    if os_type == 'Linux': name = 'tinyos'

    if (os_type == "Linux") or (os_type == 'Rasbian'): fname = '/home/%s/' %name
    elif os_type == 'Win' :
        fname = '/home/tinyos/' #수동설정해야 함
    elif os_type == "Darwin":
        fname = '/Users/%s/' %name
        sshpass = '/usr/local/bin/'

    fname = './out/%s_cron.txt' %(hostn[:-1])

    writefile (info, fname)
    checkifexist(fname)

    #print ("finish and return string")
    print (info)
