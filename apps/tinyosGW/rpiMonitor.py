# -*- coding: utf-8 -*-
#!/usr/bin/python3
"""
rpiMonitor.py : monitoring on raspberry pi
"""

import os

## function disk_usage : return disk usage info at numbers
# all : total disk usage at list
# free : free disk usage at int
# used : used disk usage at int
def disk_usage(path, diskUsage='all'):
    st = os.statvfs(path)
    free = st.f_bavail * st.f_frsize
    total = st.f_blocks * st.f_frsize
    used = (st.f_blocks - st.f_bfree) * st.f_frsize

    if diskUsage == 'free':
        diskUsage = free
    elif diskUsage == 'total':
        diskUsage = total
    elif diskUsage == 'used':
        diskUsage = used
    elif diskUsage == 'all':
        diskUsage = free, total, used
    else:
        diskUsage = None

    return diskUsage

def get_route():
    p = os.popen("route -n")
    return p.read()

## funtion get_hostname : return raspberry pi hostname info 
def get_hostname():
    p = os.popen("hostname")
    return p.read()

def get_pip():
    cmd = "curl http://checkip.amazonaws.com"
    ip = os.popen(cmd).read()
    return ip

def get_proxy():
    p = os.popen("cat /lib/systemd/system/reverseProxy.service | grep autossh")
    return p.read()

## function get_df : return disk usage info
def get_df(valueflag=False):
    p = os.popen("df -h")
    return p.read()

## funtion get_free : return memory usage info
def get_free(valueflag=False):
    if not  valueflag:
        p = os.popen("free")
    else:
        p = os.popen("free|grep Mem|grep -v grep|awk '{ print $4 }'")
    return p.read()

## function get_uptime : return working time of raspberry pi
def get_uptime():
    p = os.popen("uptime")
    return p.read()

## function get_ifconfig : return network interfaces info
def get_ifconfig(valueflag=False):
    p = os.popen("ifconfig")
    return p.read()

## function get_stalk_status : return stalk service info
def get_stalk_status():
    p = os.popen("stalk status")
    return p.read()

def get_proc_cpu(proc):
    str_proc ="ps -e -o pcpu,cmd --no-headers|grep %s|grep -v grep|awk '{sum += $1} END {print sum}'" % proc
    p = os.popen(str_proc)
    try:
        return float(p.read())
    except ValueError:
        return None

def get_proc_mem(proc):
    str_proc ="ps -e -o pmem,cmd --no-headers|grep %s|grep -v grep|awk '{sum += $1} END {print sum}'" % proc
    p = os.popen(str_proc)
    try:
        return float(p.read())
    except ValueError:
        return None

if __name__ == '__main__':
    print(disk_usage('/', 'free'))
    print(get_df())
    print(get_pip())
    print(get_free())
    print(get_uptime())
    print(get_hostname())
    print(get_proc_cpu("python"))
    print(get_proc_mem("python"))
