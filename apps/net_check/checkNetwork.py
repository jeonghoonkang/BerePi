#!/usr/bin/python3

import os, time
import subprocess
import urllib

def network_on():
    try:
        urllib.request.urlopen('http://1.1.1.1', timeout=1)
        return True
    #except urllib.error.URLError as err:
    except:
        return False

def traceroute_log():
    hostname = '1.1.1.1'
    res = subprocess.check_output(['traceroute', hostname])
    return res.decode('utf-8')

def file_log(contents):
    t = time.time()
    #now = time.strftime("%y%m%d_%H%M%S", time.localtime(t))
    now = time.strftime("H%M%S", time.localtime(t))
    today = time.strftime("%y%m%d", time.localtime(t))

    filename = 'NetworkLog_%s.log' % today
    f = open(filename, 'w')
    c = "\n-----\n%s\n" % now
    f.write(c)
    #f.write(contents)
    for c in contents:
        f.write(c)
    f.close()

def main():
    if network_on():
        print("not working network...")
        fileLog = traceroute_log()
        #print(fileLog)
        file_log(fileLog)


if __name__ == "__main__":
    while True:
        main()
        time.sleep(5 * 60)
