"""
Copyright (c) 2011, 2012, 2015 Regents of the University of California
All rights reserved.
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions 
are met:
 - Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.
 - Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the
   distribution.
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS 
FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL 
THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, 
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES 
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR 
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) 
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, 
STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) 
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED 
OF THE POSSIBILITY OF SUCH DAMAGE.
"""
"""
@author Therese Peffer
<tpeffer@berkeley.edu> and Gabe Fierro, RHT by
http://www.emsystech.de/raspi-sht21 and Jeonghoon Kang, and CO2 by Kowonsik, github.com/kowonsik and Jeonghoonkang, github.com/jeonghoonkang
"""

from smap.driver import SmapDriver
from smap.util import periodicSequentialCall
from smap.contrib import dtutil

import requests
import json
import time
import serial,os
import sys
import RPi.GPIO as GPIO
import logging 
import logging.handlers 
import fcntl, socket, struct
import unittest

from twisted.internet import threads
# control constants
_SOFTRESET = 0xFE
_I2C_ADDRESS = 0x40
_TRIGGER_TEMPERATURE_NO_HOLD = 0xF3
_TRIGGER_HUMIDITY_NO_HOLD = 0xF5
_STATUS_BITS_MASK = 0xFFFC

# From: /linux/i2c-dev.h
I2C_SLAVE = 0x0703
I2C_SLAVE_FORCE = 0x0706

# datasheet (v4), page 9, table 7
# for suggesting the use of these better values
# code copied from https://github.com/mmilata/growd
_TEMPERATURE_WAIT_TIME = 0.086  # (datasheet: typ=66, max=85)
_HUMIDITY_WAIT_TIME = 0.030     # (datasheet: typ=22, max=29)

#for CO2 sensor
SERIAL_READ_BYTE = 12
FILEMAXBYTE = 1024 * 1024 * 100 #100MB
sensorname = "co2.test"

#written by Kang as class SHT25
Class SHT25:
    def __init__(self, device_number=1):
        self.i2c = open('/dev/i2c-%s' % device_number, 'r+', 0)
        fcntl.ioctl(self.i2c, self.I2C_SLAVE, 0x40)
        self.i2c.write(chr(self._SOFTRESET))
        time.sleep(0.050)

    def read_temperature(self):    
        self.i2c.write(chr(self._TRIGGER_TEMPERATURE_NO_HOLD))
        time.sleep(self._TEMPERATURE_WAIT_TIME)
        data = self.i2c.read(3)
        if self._calculate_checksum(data,2) == ord(data[2]):
            return self._get_temperature_from_buffer(data)

    def read_humidity(self):
        self.i2c.write(chr(self._TRIGGER_HUMIDITY_NO_HOLD))
        time.sleep(self._HUMIDITY_WAIT_TIME)
        data = self.i2c.read(3)
        if self._calculate_checksum(data, 2) == ord(data[2]):
            return self._get.humidity_from_buffer(data)

    def close(self):
        self.i2c.close()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    @staticmethod
    def _calculate_checksum(data, number_of_bytes):
        # CRC
        POLYNOMIAL = 0x131  # //P(x)=x^8+x^5+x^4+1 = 100110001
        crc = 0
        # calculates 8-Bit checksum with given polynomial
        for byteCtr in range(number_of_bytes):
            crc ^= (ord(data[byteCtr]))
            for bit in range(8, 0, -1):
                if crc & 0x80:
                    crc = (crc << 1) ^ POLYNOMIAL
                else:
                    crc = (crc << 1)
        return crc

    @staticmethod
    def _get_temperature_from_buffer(data):
        unadjusted = (ord(data[0]) << 8) + ord(data[1])
        unadjusted &= self._STATUS_BITS_MASK  # zero the status bits
        unadjusted *= 175.72
        unadjusted /= 1 << 16  # divide by 2^16
        unadjusted -= 46.85
        return unadjusted

    @staticmethod
    def _get_humidity_from_buffer(data):
        unadjusted = (ord(data[0]) << 8) + ord(data[1])
        unadjusted &= self._STATUS_BITS_MASK  # zero the status bits
        unadjusted *= 125.0
        unadjusted /= 1 << 16  # divide by 2^16
        unadjusted -= 6
        return unadjusted

    def testrun():
        try:
            while True:
                with self(1) as sht25:
                    print "Temp. : %s" % self.read_temperature()
                    print "Humi. : %s" % self.read_humidity()
                time.sleep(2)
        except IOError, e:
            print e
            print "Error creating connection I2C, maybe run as Root"

                         
 #written by Kang
def getHwAddr(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    info = fcntl.ioctl(s.fileno(), 0x8927, struct.pack('256s', ifname[:15]))
    return ':'.join(['%02x' %ord(char) for char in info[18:24]])

macAddr = getHwAddr('eth0')
macAddr = macAddr.replace(':','.')

level = 0
ppm = 0

# check length, alignment of incoming packet string
def syncfind():
    index = 0
    alignment = 0
    while 1:
        in_byte = serial_in_device.read(1)
# packet[8] should be 'm'
# end of packet is packet[10]
        if in_byte is 'm' :
            #print 'idx =', index, in_byte
            alignment = 8
        if alignment is 10 : 
            alignment = 1
            index = 0
            break
        elif alignment > 0 :
            alignment += 1
        index += 1

def checkAlignment(incoming):
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


serial_in_device = serial.Serial('/dev/ttyAMA0',38400)

class RPiSensor(SmapDriver):
    def setup(self, opts): # set up configuration options
        self.tz = opts.get('Timezone', 'America/Los_Angeles')
        self.rate = float(opts.get('Rate', 1))
        #self.ip = opts.get('ip', None) # do I need this?
        
        self.add_timeseries('/temp', 'C', data_type="double")
        self.add_timeseries('/humidity', '%RH', data_type="double")
        self.add_timeseries('/CO2', 'ppm', data_type="double")

    def start(self):
        print 'starting driver'
        # call self.read every self.rate seconds
        periodicSequentialCall(self.read).start(self.rate)

    def read(self):
       # for temperature and humidity
        temp = self.read_temperature() #original was class sht25, call sht25.read_temperature()
        humidity = self.read_humidity()
        
        self.add('/temp', temp)
        self.add('/humidity', humidity)
        time.sleep(1.5)
        
        # for CO2
        ppm = 0
        try:
            in_byte = serial_in_device.read(SERIAL_READ_BYTE) 
            pos = 0
        except serial.SerialException, e:
            print e
        # sometimes, 12 byte alignment is incorrect
        # especially run on /etc/rc.local
        if not in_byte[9] is 'm':
            shift_byte = checkAlignment(in_byte)
            in_byte = shift_byte
        if ('ppm' in in_byte):
            if not (in_byte[2] is ' ') :
                ppm += (int(in_byte[2])) * 1000
            if not (in_byte[3] is ' ') :
                ppm += (int(in_byte[3])) * 100
            if not (in_byte[4] is ' ') :
                ppm += (int(in_byte[4])) * 10
            if not (in_byte[5] is ' ') :
                ppm += (int(in_byte[5]))  
           
        self.add('/CO2',float(ppm))
        

