# -*- coding: utf-8 -*-
## Author : jeonghoon.kang@gmail.com

## This code for T110, ELT CO2 sensor
## Please see details for the CO2 sensor data sheet : http://eltsensor.co.kr/2012/eng/pdf/T-110/DS_T-110-3V_ver1.210.pdf

import serial,os,time
import sys
import RPi.GPIO as GPIO
#import logging 
#import logging.handlers 

#import json
#import requests
#import fcntl, socket, struct

class T110:
    SERIAL_READ_BYTE = 12

    ppm = 0

    # open RASPI serial device, 38400
    def __init__(self):
    	'''
	    GPIO.setwarnings(False)
	    GPIO.cleanup()
	    GPIO.setmode(GPIO.BCM)
	    GPIO.setup(18, GPIO.OUT)
	    GPIO.setup(23, GPIO.OUT)
	    GPIO.setup(24, GPIO.OUT)
	    GPIO.setup(25, GPIO.OUT)

	    self.serial_in_device = serial.Serial('/dev/ttyAMA0',38400)
        '''
	pass

    def close(self):
        GPIO.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def checkAlignment(self, incoming):
	idxNum = incoming.find('m')
	# idxNum is 9, correct
	offset = idxNum - 9	
	if offset > 0 :
		new_str = incoming[offset:]
		new_str = new_str + incoming[:offset]
	if offset < 0 :
		offset = 12 + offset 
		new_str = incoming[offset:]
		new_str = new_str + incoming[:offset]
	return new_str

    def read_co2(self):
	    GPIO.setwarnings(False)
	    GPIO.cleanup()
	    GPIO.setmode(GPIO.BCM)
	    GPIO.setup(18, GPIO.OUT)
	    GPIO.setup(23, GPIO.OUT)
	    GPIO.setup(24, GPIO.OUT)
	    GPIO.setup(25, GPIO.OUT)

	    self.serial_in_device = serial.Serial('/dev/ttyAMA0',38400)

	    in_byte = self.serial_in_device.read(self.SERIAL_READ_BYTE)

	    if not (len(in_byte) is self.SERIAL_READ_BYTE):
		return False

	    if not in_byte[9] is 'm':
		shift_byte = self.checkAlignment(in_byte)
		in_byte = shift_byte

	    if ('ppm' in in_byte):
		self.ppm = self._get_buffer(in_byte)
	    else:
		self.ppm = False
	    print self.ppm

	    return self.ppm

    def _get_buffer(self, _buffer):
   	    ppm = 0
	    if not (_buffer[2] is ' '):
		ppm += (int(_buffer[2])) * 1000
	    if not (_buffer[3] is ' '):
		ppm += (int(_buffer[3])) * 100
	    if not (_buffer[4] is ' '):
		ppm += (int(_buffer[4])) * 10
	    if not (_buffer[5] is ' '):
		ppm += (int(_buffer[5]))  
	    print ppm
	    return ppm


if __name__ == "__main__":
  t110 = T110()
  while True:
	  try:
	    result = t110.read_co2()
	    print "co2: %s ppm" % result
	    time.sleep(1)
	  except IOError, e:
	    print e
