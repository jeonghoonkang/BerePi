# Author : Jeonghoonkang, github.com/jeonghoonkang
# -*- coding: utf-8 -*-

import serial,os,time
import sys
import fcntl, socket, struct

lineCnt = 0

def getHwAddr(ifname):
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	info = fcntl.ioctl(s.fileno(), 0x8927, struct.pack('256s', ifname[:15]))
	return ':'.join(['%02x' %ord(char) for char in info[18:24]])

def init():
    macAddr = getHwAddr('eth0')
    macAddr = macAddr.replace(':','.')
    print " # eth0 HW MAC addr is " + macAddr

if __name__== "__main__" :

    if len(sys.argv) is 1:
        print " # RaspberryPi2 SW "
        print " # Serial Byte read and print "
        print " # Default serial device is /dev/ttyAMA0 "
        print " # example : python serial_byte.py 115200 "
        exit(1)

    init()
    rate = sys.argv[1]

    try:
        # open RASPI serial device, 38400
        # Check speed 38400 or 115200, 9800
        serial_in_device = serial.Serial('/dev/ttyAMA0', rate)

    except serial.SerialException, e:
        print " << Serial open error"
        exit(1)
    
    print " >> Serial Open Complete "

    while True:
        lineCnt += 1
        try:
            in_byte = serial_in_device.read(1) 
            print " [cnt: %3d] " %lineCnt, (in_byte)
        except serial.SerialException, e:
            print e
            print " [cnt: %3d]" %lineCnt, " << Serial read error"
            exit(0)
