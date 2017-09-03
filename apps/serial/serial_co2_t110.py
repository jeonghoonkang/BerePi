## This serial code for T110, ELT CO2 sensor
## Please see details for the CO2 sensor data sheet : http://eltsensor.co.kr/2012/eng/pdf/T-110/DS_T-110-3V_ver1.210.pdf
## Author : jeonghoon.kang@gmail.com

import serial,os,time
import sys
import fcntl, socket, struct

DEBUG_PRINT = 1
SERIAL_READ_BYTE = 12

def getHwAddr(ifname):
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	info = fcntl.ioctl(s.fileno(), 0x8927, struct.pack('256s', ifname[:15]))
	return ':'.join(['%02x' %ord(char) for char in info[18:24]])

def init():
    macAddr = getHwAddr('eth0')
    macAddr = macAddr.replace(':','.')

if __name__== "__main__" :
    init()
    try:
        # open RASPI serial device, 38400
        # Check speed 38400 or 115200, 9800
        serial_in_device = serial.Serial('/dev/ttyAMA0', baudrate=38400)
    except serial.SerialException, e:
        print " << Serial open error"
        exit(1)
    print " >> Serial Open Complete "
    lineCnt = 0

    while True:
        lineCnt += 1
        try:
            in_byte = serial_in_device.read(1) 
            print "[cnt: %3d] " %lineCnt, (in_byte)
        except serial.SerialException, e:
            print e
            print "[cnt: %3d]" %lineCnt, " << serial read error"
            exit(0)
