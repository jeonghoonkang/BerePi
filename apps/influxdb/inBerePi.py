#!/usr/bin/python
# -*- coding: utf-8 -*-

import time, json, math
import socket
import tsdb
import lib.sht25 as sht25

def influxdbwrite(obj=None):
	ctx = {}
        dt = (1.0 / 1000) * 1000000  # to microseconds

        ctx['time'] = int(time.time() * 1000000)  # to microseconds
        ctx['id'] = str(1)

	measurement = "%s.%s" % (obj['hostname'], obj['type'])
	metadata = "\
		device= rpi2,\
		sensor= sht20,\
		user=   sinbinet\
	"
	metadata = metadata.replace(" ", "") 

	tr = tsdb.Transaction(measurement)
	tr.write(value=obj['value'], tag=obj['type'], meta=metadata, timestamp=ctx['time'])
	tr.flush()

def readData():
	data = {}
	th = sht25.SHT25()

	temp = th.read_temperature()
	humi = th.read_humidity()

	data['hostname'] = socket.gethostname()
	data['value'] = temp
	data['type'] = 'temp'
	influxdbwrite(data)
	time.sleep(.1)

	data['value'] = humi
	data['type'] = 'humi'
	influxdbwrite(data)

	print temp, humi

if __name__ == "__main__":
	while True:
		readData()
		time.sleep(10)
