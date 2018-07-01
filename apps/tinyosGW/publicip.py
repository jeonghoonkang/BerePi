#-*- coding: utf-8 -*-
#!/usr/bin/python
# Author : jeonghoonkang, https://github.com/jeonghoonkang

from __future__ import print_function
from subprocess import *
from types import *
import platform
import sys
import os

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
    print (ip)
    return ip

def getiip():

    cmd="/sbin/ifconfig"
    _os_type = platform.system()
    print (_os_type)
    if _os_type.find('Cygwin') > 0:
        cmd = "ipconfig"
    iip = run_cmd(cmd)
    return iip, _os_type

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
    print (msg)

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

    ip, port, id, passwd = args_proc()

    p_ip = getip()
    i_ip, os_type = getiip()
    info = i_ip + p_ip
    hostn = hostname()
    name = os.getlogin()

    if os_type == "Linux":
        fname = '/home/%s/' %name
    elif os_type == "Darwin": 
        fname = '/Users/%s/' %name

    fname += 'devel/BerePi/apps/tinyosGW/out/%s.txt' %(hostn[:-1])

    writefile (info, fname)
    checkifexist(fname)

    cmd = 'sshpass -p' + passwd + ' ' + 'scp' + ' -o' + ' StrictHostKeyChecking=no'
    cmd += " %s " %fname + '%s@%s:' %(id,ip) + '/var/www/html/server/'
#    cmd = 'scp'  
#    cmd += " %s " %fname + '%s@%s:' %(id,ip) + '/var/www/html/server/'
    ret = run_cmd(cmd)
    print (cmd)
    print (" ")
    print (ret)

# ssh-keygen
# cat ~/.ssh/id_rsa.pub | ssh -p xxxx pi@xxx.xxx.xxx 'cat >>
# .ssh/authorized_keys'
