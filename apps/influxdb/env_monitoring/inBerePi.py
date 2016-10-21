#!/usr/bin/python
# -*- coding: utf-8 -*-

import time, json, math
import socket
import sys
import tsdb
sys.path.append('../../sdb/')
import sht25
import lib.t110 as t110

ID = 17
MEASUREMENT = "sensing"

def influxdbwrite(obj=None):
	global MEASUREMENT

	ctx = {}
        dt = (1.0 / 1000) * 1000000  # to microseconds

        ctx['time'] = int(time.time() * 1000000)  # to microseconds
        ctx['id'] = str(1)

	tr = tsdb.Transaction(MEASUREMENT)
	tr.write(value=obj['value'], tag=obj['tag'], timestamp=ctx['time'])
	tr.flush()

def get_TH(sensor, t=None):
	try:
		if t is 1:
			temp = sensor.read_temperature()
			return temp
		elif t is 2:
			humi = sensor.read_humidity()
			return humi
		else:
			return False
	except:
		return False

def get_CO2(sensor):
	try:
		co2 = sensor.read_co2()
		return float(co2)
		#return co2
	except:
		return False

def readData():
	global ID
	data = {}
	th = sht25.SHT25()
	cdo = t110.T110()

	while True:
		data['hostname'] = socket.gethostname()
		data['tag'] = {
			'id' 	   : ID,
			'type'     : '',
			'location' : 'sinbinet',
		}

		temp = get_TH(th, 1)
		if temp:
			data['value'] = temp
			data['tag']['type'] = 'temp'
			influxdbwrite(data)
			time.sleep(.1)

		humi = get_TH(th, 2)
		if humi:
			data['value'] = humi
			data['tag']['type'] = 'humi'
			influxdbwrite(data)
			time.sleep(.1)

		co2 = get_CO2(cdo)
		print "CO2 : %s" % co2
		print type(co2)
		if co2:
			data['value'] = co2
			data['tag']['type'] = 'co2'
			influxdbwrite(data)

		print temp, humi, co2
		time.sleep(10)

if __name__ == "__main__":
	readData()
