# -*- coding: utf-8 -*-
# __init__.py

import time
import traceback
import json

#from influxdb.influxdb08 import client as influxdb
from influxdb import InfluxDBClient as influxdb

import logger

__tsdb_client = None


def influx_client():
    global __tsdb_client
    if not __tsdb_client:
        #__tsdb_client = influxdb.InfluxDBClient('localhost', 8086, 'pdmuser', 'pdmuser', 'pdm')
        __tsdb_client = influxdb('localhost', 8086, 'root', 'root', 'sensing')

    return __tsdb_client


class Transaction(object):
    def __init__(self, measurement):
        assert isinstance(measurement, str)
        super(Transaction, self).__init__()
        self.__measurement = measurement
        self.__points = []

    def write(self, value=0, meta=None, tag={"tag":None}, timestamp=None):
        assert isinstance(value, (int, long, float))
        #assert meta is None or isinstance(meta, (str, unicode))
        assert timestamp is None or isinstance(timestamp, (int, long))
        assert isinstance(tag, dict)

        if timestamp is None:
            t = int(time.time() * 1000000 * 1000)  # to microseconds
        else:
            if len(str(timestamp)) == 10:  # seconds
                t = timestamp * 1000000 * 1000
            elif len(str(timestamp)) == 13:  # mili
                t = timestamp * 1000 * 1000
            elif len(str(timestamp)) == 16:  # micro
                t = timestamp * 1000
            elif len(str(timestamp)) == 19:  # nano
                t = timestamp
            else:
                assert False

	self.__time = t
	self.__value = value
	self.__meta = meta
	self.__tag = tag 
        self.__points.append([t, value, meta])

    def flush(self):
        if self.__points:
            try:
                data = [
                  {
                    "measurement": self.__measurement,
                    "tags": self.__tag,
	            "time": self.__time,
                    "fields": {
		        "reading": self.__value,
	            },
                  }
	        ]
                #influx_client().write_points(data, 'u')
                influx_client().write_points(data)
                logger.info(__name__, 'sent %d data points to %s' % (len(self.__points), self.__measurement))
                self.__points = []

            except Exception:
                traceback.print_exc()
                logger.info('RECOVERY', 'influxDB:write_points:%s' % json.dumps(data))

    def drop(self):
        self.__points = []
        logger.info(__name__, 'dropped %d data points for %s' % (len(self.__points), self.__measurement))
