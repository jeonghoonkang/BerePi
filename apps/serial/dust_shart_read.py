# -*- coding: utf-8 -*-
# Author : Jeonghoonkang, github.com/jeonghoonkang
# https://github.com/sharpsensoruser/sharp-sensor-demos/wiki/Application-Guide-for-Sharp-GP2Y1030AU0F-Dust-Sensor


import serial,os,time
import sys
import fcntl, socket, struct


def getHwAddr(ifname):
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	info = fcntl.ioctl(s.fileno(), 0x8927, struct.pack('256s', ifname[:15]))
	return ':'.join(['%02x' %ord(char) for char in info[18:24]])

def init():
    macAddr = getHwAddr('eth0')
    macAddr = macAddr.replace(':','.')
    print " # eth0 HW MAC addr is " + macAddr

def get_pm25(pack):
    pma = pack[4:8]
    pma_int = int(pma[0:2],16)*256 + int(pma[2:4],16)

    print "PM 2.5 =", pma_int
    print "*"*pma_int
    print "="*50

def get_dust(pack):
    pma = pack[12:16]
    pma_int = int(pma[0:2],16)*256 + int(pma[2:4],16)

    print "Dust=", pma_int
    print "*"*pma_int
    print "="*100

def start_sensing(serial_in_device):

    byteCnt = 0
    in_packet_buf = ''
    sync_packet_buf = ''
    val = 0

    while True:
        byteCnt += 1
        try:
            str_byte = serial_in_device.read(1).encode('hex') 

            if sync_packet_buf[:4] == 'fffa':
                sync_packet_buf += str_byte
                #print sync_packet_buf
                if len(sync_packet_buf) == 20: 
                    val = get_pm25(sync_packet_buf)
                    #val = get_dust(sync_packet_buf)
                    sync_packet_buf = ''
                    return

            in_packet_buf += str_byte
            #print in_packet_buf

            if len(in_packet_buf) > 100:
                in_packet_buf = ''

            if in_packet_buf != '':
                sync_pos = in_packet_buf.find('fffa')
                # find returns 1 if there it is

            if sync_pos > 0 :
                sync_packet_buf = in_packet_buf[sync_pos:]
                in_packet_buf = ''
                sync_pos = 0
                #print sync_packet_buf

        except serial.SerialException, e:
            print e
            print " [cnt: %d]" %byteCnt, " << Serial read error"
            exit(0)

if __name__== "__main__" :

    if len(sys.argv) is 1:
        print " # RaspberryPi2 SW "
        print " # Serial Byte read and print "
        print " # Default serial device is /dev/ttyserial0 "
        print " # example : python serial_byte.py 115200 "
        exit(1)

    init()
    rate = sys.argv[1]

    try:
        # open RASPI serial device, 38400
        # Check speed 38400 or 115200, 9800
        serial_in_device = serial.Serial('/dev/serial0', rate)

    except serial.SerialException, e:
        print " << Serial open error"
        exit(1)
    
    print " >> Serial Open Complete "

    while True:
        start_sensing(serial_in_device)
        time.sleep(10)
