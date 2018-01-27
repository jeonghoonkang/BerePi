
#!/usr/bin/python
# -*- coding: utf-8 -*-
# Author : jeonghoonkang, https://github.com/jeonghoonkang

#server program
import socket
import threading
import time
import sys

cnt = 0

HOST = ''
PORT = 8086
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind((HOST, PORT))
s.listen(3)
conn, addr = s.accept()

print(' '*10, 'Connected by', addr)

# def sendingMsg():
# 	while True:
# 		data = input()
# 		data = data.encode("utf-8")
# 		conn.send(data)
# 	conn.close()


def gettingMsg():
    global cnt
    rcount = 0
    rcvbuf=''
    writing=''
    outfile = "receive_data.txt"
    while True:
        data = conn.recv(1000*1024)
        #print data[:100]
        rcount += 1
        if not data:
            break
        else:
            # data = str(data).split("b'", 1)[1].rsplit("'",1)[0]
            # data = data.decode("utf-8","ignore")
            pos = data.find("node_id")
            #print 'pos=', pos
            if pos != -1:
                print rcvbuf
                writing = rcvbuf
                cnt = 0
                rcvbuf = ''
            rcvbuf += data
       #insertdb(writing) 
    conn.close()


threading._start_new_thread(gettingMsg,())


while True:
    
    cnt += 1
    time.sleep(1)
    pout = "... dummy loop, %s \r" %cnt
    sys.stdout.write(pout)
    sys.stdout.flush()
    pass
