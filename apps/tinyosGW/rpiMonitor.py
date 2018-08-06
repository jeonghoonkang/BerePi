#!/usr/bin/python
"""
rpiMonitor.py : monitoring on raspberry pi
"""

import os

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

def gethostname():
    p = os.popen("hostname")
    return p.read()

def getdf():
    p = os.popen("df -h")
    return p.read()

def getfree():
    p = os.popen("free")
    return p.read()

def getuptime():
    p = os.popen("uptime")
    return p.read()

def getstalkstatus():
    p = os.popen("stalk status")
    return p.read()

def getprocCpu(proc):
    str_proc ="ps -e -o pcpu,cmd --no-headers|grep %s|grep -v grep|awk '{sum += $1} END {print sum}'" % proc
    p = os.popen(str_proc)
    try:
        return float(p.read())
    except ValueError:
        return None

def getprocMem(proc):
    str_proc ="ps -e -o pmem,cmd --no-headers|grep %s|grep -v grep|awk '{sum += $1} END {print sum}'" % proc
    p = os.popen(str_proc)
    try:
        return float(p.read())
    except ValueError:
        return None

print disk_usage('/', 'free')
print getdf()
print getfree()
print getuptime()
print gethostname()
print getprocCpu("python")
print getprocMem("python")
