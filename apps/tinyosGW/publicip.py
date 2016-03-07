#!/usr/bin/python
# Author : jeonghoonkang, https://github.com/jeonghoonkang
#-*- coding: utf-8 -*-

from subprocess import *
# 입력

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
    ip = getip()
    print "My Public IP is ", ip
    cmd = "mkdir -p /home/tinyos/my_deamon/output"
    print run_cmd(cmd)
    cmd = "cd /home/tinyos/my_deamon/output"
    print run_cmd(cmd)
    #cmd = "touch /home/tinyos/my_deamon/output"
    cmd_100 = "ssh pi@iptime.org "
    cmd_010 = "cd my_deamon/output && echo %s is Lab Server Room IP " %ip[:-1]
    cmd_001 = " | cat > ip.html" 
    cmd = cmd_010 + cmd_001  
    print run_cmd(cmd)

    cmd_200 = "scp pi@iptime.org "
    cmd = "scp" + " ip.html" + " pi@iptime.org:" + "www/cog" 
    print cmd
    print run_cmd(cmd)

    
