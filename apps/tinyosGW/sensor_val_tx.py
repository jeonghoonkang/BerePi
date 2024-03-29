#-*- coding: utf-8 -*-
#!/usr/bin/python
# Author : jeonghoonkang, https://github.com/jeonghoonkang

from __future__ import print_function
from subprocess import *
from types import *
import platform
import sys
import os
import datetime

import tailer

def run_cmd(cmd):
    p = Popen(cmd, shell=True, stdout=PIPE)
    output = p.communicate()[0]
    return output

def hostname():
    cmd = "hostname"
    ret = run_cmd(cmd)
    return ret

def get_measure():
    cmd="/sbin/ifconfig"
    _os_type = platform.system()

    _os_ver = os.uname()
    #print ( ' FIRST :' , _os_ver[0])
    #print ( ' LAST :' , _os_ver[-1])
    
    if (_os_ver[0] == 'Linux') :
        if (_os_ver[-1] == 'x86_64') :
            _os_type = 'Linux'
            cmd = "/sbin/ifconfig"

    print ('os-type', _os_type)
    if _os_type.find('Cygwin') > 0:
        cmd = "ipconfig"
    iip = run_cmd(cmd)
    #print (iip)
    return iip, _os_type

def checkifexist(fname):
    cmd='ls ' + fname
    print (run_cmd(cmd))

def writefile_list(_in, fn="ip.txt"):
    f = open(fn, 'w')
    tin = "\n".join(_in)
    print(tin)
    f.write(tin)
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

    print ('\n', datetime.datetime.now(), '\n')
    ip, port, id, passwd = args_proc()

    m, os_type = get_measure()
    info = m
    
    hostn = hostname()
    try : name = os.getlogin()
    except :
        print ('[exception] get log-in user name')
        name = 'pi' #라즈베리파이 경우 pi로 입력 작성. ubuntu는 사용자
        # crontab 으로 실행할때는. getloin()에서 예외 발생하여, 이 부분에 정확한 아이디를 넣어줘야함
        # 아이디가 정확하지 않으면 실행 에러로 종료됨
        # 확인필수  : https://github.com/jeonghoonkang/BerePi/blob/master/apps/tinyosGW/debug/debug.log
    print ("using local id : ", name)

    sshpass = ''
    if os_type == "Linux":
        fname = '/home/%s' %name
    elif os_type == 'Win' :
        fname = '/home/tinyos' #수동설정해야 함
    elif os_type == "Darwin":
        fname = '/Users/%s' %name
        sshpass = '/usr/local/bin/'

    log_file_loc = '%s/devel/BerePi/logs/berelogger_%s.log' %(fname,hostn[:-1])
    checkifexist(log_file_loc)

    lines = tailer.tail(open(str(log_file_loc)),40)
    print(lines, type(lines))

    writefile_list (lines, './tmp.log')

    cmd = sshpass + 'sshpass -p' + passwd + ' ' + 'scp' + ' -P%s'%port + ' -o' + ' StrictHostKeyChecking=no'
    cmd += " tmp.log " + '%s@%s:' %(id,ip) + '/var/www/html/sensor/sensor_dust_%s.log ' %hostn[:-1]
    #cmd = 'scp'
    #cmd += " %s " %fname + '%s@%s:' %(id,ip) + '/var/www/html/server/'
    print (cmd)
    print ( 'return of os.system = ', os.system(cmd) )

    #ret = run_cmd(cmd)
    print ("finish ")
    #print (ret)

# ssh-keygen
# cat ~/.ssh/id_rsa.pub | ssh -p xxxx pi@xxx.xxx.xxx 'cat >>
# .ssh/authorized_keys'
