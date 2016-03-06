#!/usr/bin/python
# Author : jeonghoonkang, https://github.com/jeonghoonkang
#-*- coding: utf-8 -*-

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
