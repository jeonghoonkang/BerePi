## This code for LED BD 00

import serial,os,time
import sys
import RPi.GPIO as GPIO
import logging
import json
import requests
import socket
import fcntl
import struct

debug_print = 0

level = 0
ppm = 0

# important, sensorname shuould be pre-defined, unique sensorname
bdname = "led.00"

url = "http://xx.xx.xx.xx:4242/api/put"

def getHwAddr(ifname):
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	info = fcntl.ioctl(s.fileno(), 0x8927, struct.pack('256s', ifname[:15]))
	return ':'.join(['%02x' %ord(char) for char in info[18:24]])

macAddr = getHwAddr('eth0')
macAddr = macAddr.replace(':','.')


logging.basicConfig(filename='/home/pi/log_led1_test.log',level=logging.DEBUG)
logging.info("Start------------------------------- ")

bled = 16
gled = 20
rled = 21
# HW setup, GPIO
GPIO.cleanup()
GPIO.setmode(GPIO.BCM)
GPIO.setup(bled, GPIO.OUT)
GPIO.setup(gled, GPIO.OUT)
GPIO.setup(rled, GPIO.OUT)
GPIO.output(bled, True)
GPIO.output(gled, True)
GPIO.output(rled, True)
time.sleep(1)
logging.info('---->>>> GPIO all set ')


def ledb_on():
    GPIO.output(bled, True)
def ledg_on():
    GPIO.output(gled, True)
def ledr_on():
    GPIO.output(rled, True)
def ledb_off():
    GPIO.output(bled, False)
def ledg_off():
    GPIO.output(gled, False)
def ledr_off():
    GPIO.output(rled, False)
def ledall_off():
    GPIO.output(bled, False)
    GPIO.output(gled, False)
    GPIO.output(rled, False)

led_time_idx = 0

while True:
    led_time_idx += 1
    if ((led_time_idx % 3) == 0) :
        logline = bdname + 'LED is '
        now = time.localtime()
        now_str = "%04d-%02d-%02d %02d:%02d:%02d" % (now.tm_year, now.tm_mon, now.tm_mday, now.tm_hour, now.tm_min, now.tm_sec)
        logline += now_str
        logging.warning("logline = %s", logline)
        logline = ""
        ledall_off()
        ledb_on()
    elif ((led_time_idx % 3) == 1) :
        ledall_off()
        ledg_on()
    elif ((led_time_idx % 3) ==  2) :
        ledall_off()
        ledr_on()

    time.sleep(1)

GPIO.cleanup()
