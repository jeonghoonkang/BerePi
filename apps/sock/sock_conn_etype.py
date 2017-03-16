
#!/usr/bin/python
# -*- coding: utf-8 -*-
# Author : jeonghoonkang, https://github.com/jeonghoonkang


import socket
import os
import sys
import struct
import time

ETYPE_VALUE_MAX = 8000

def main():
	SERVER_ADDR = "127.0.0.1"
	SERVER_PORT = 4000
	print "   try connecting .... "

	sock = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
	ret_conn = sock.connect( ( SERVER_ADDR, SERVER_PORT ) )

	readBuffer = ""
	receivedLines = []
	sendLines = []

	while True:
		# provide buffer
		recv = sock.recv( 1024 )
		readBuffer += recv

        print " "*20, "Packet comming"
		print recv


if __name__ == "__main__":
    main()
