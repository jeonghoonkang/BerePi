#!/usr/bin/python
"""
disk_usage : Return disk usage, in bytes
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

def getdf():
    p = os.popen("df -h")
    return p.read()

def getfree():
    p = os.popen("free")
    return p.read()

def getuptime():
    p = os.popen("uptime")
    return p.read()


print disk_usage('/', 'free')
print getdf()
print getfree()
print getuptime()
