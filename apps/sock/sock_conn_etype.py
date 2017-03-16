
#!/usr/bin/python
# -*- coding: utf-8 -*-
# Author : jeonghoonkang, https://github.com/jeonghoonkang

# 동작 안함 확인 필요 

from socket import *
import os
import sys
import struct
import time

ETYPE_VALUE_MAX = 8000


def main():

    splug_acc_flag = 0
    etype_acc_flag = 0

    #SERVER_ADDR = "222.239.78.8"
    #SERVER_PORT = 8283   # 40001 samho  9293 hana
    HOST=''
    LOCAL_PORT = 4000
    con_add = (HOST,LOCAL_PORT)

    sock = socket(AF_INET,SOCK_STREAM )
    print sock
    ret = sock.bind(con_add)
    print ret

    sock.listen(100)

    conn, addr = sock.accpet()


    print " "*10, "connected by sock client", addr


    readBuffer = ""
    receivedLines = []
    sendLines = []
    while True:
    # provide buffer
        recv = conn.recv( 1024 )
        readBuffer += recv
        print readBuffer

if __name__ == "__main__":
    main()
