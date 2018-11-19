# -*- coding: utf-8 -*-
# author : http://github.com/jeonghoonkang

import argparse
import datetime
from influxdb import InfluxDBClient

def getTSnow():
    dtnow = datetime.datetime.now()
    #print dtnow.strftime('%Y-%m-%dT%H:%M:%S')
    return dtnow.strftime('%Y-%m-%dT%H:%M:%S')

def getUTCnow():
    dtnow = datetime.datetime.utcnow()
    return dtnow.strftime('%Y-%m-%dT%H:%M:%S')

default_mname = 'public_dust'
dbname = 'kang_test'

write_json = [
    {
        "measurement": default_mname,
        "tags": {
            "host": "TOSHOME",
            "work": "public_data_insert"
        },
        #"time": "2009-11-10T23:00:00Z",
        "time": getUTCnow(),
        "fields": {
            "dust_val": -1
        }
    }
]

def main(val, measurename, host='localhost', port='8086'):
    """Instantiate a connection to the InfluxDB."""
    user = 'root'
    password = 'root'
    dbuser = 'smly'
    dbuser_password = 'my_secret_password'
    query = 'select value from cpu_load_short;'
    dbname = 'kang_test'

    client = InfluxDBClient(host, port, None, None, dbname)

    query = 'show measurements on %s;' %dbname
    print("Querying data: " + query)
    result = client.query(query)
    print("Result: {0}".format(result))
    
    write_json[0]['measurement'] = measurename
    write_json[0]['fields']['dust_val'] = val
    write_json[0]['time'] = getUTCnow()
    print("Write points: {0}".format(write_json))
    client.write_points(write_json)

    query = 'select * from %s order by desc limit 1;' %measurename
    print("Querying data: " + query)
    ''' write한 데이터가 제대로 입력되었는지 확인 '''
    result = client.query(query)
    print("Result: {0}".format(result))


def parse_args():
    """Parse the args."""
    parser = argparse.ArgumentParser(
        description='example code to play with InfluxDB')
    parser.add_argument('--host', type=str, required=False,
                        default='localhost',
                        help='hostname of InfluxDB http API')
    parser.add_argument('--port', type=int, required=False, default=8086,
                        help='port of InfluxDB http API')
    return parser.parse_args()


def influx_write(val, mname=None, host='127.0.0.1',  port=8086) :
    print " trying to connect..."
    print val, host, port 
    #to do: val, host, port, measurement 이름을 제대로 처리해야함 
    #main(host, port, val, measurename)    
    main(val, mname, host, port) 
    return True

if __name__ == '__main__':
    args = parse_args()
    #print args
    print "trying to ..."
    print args.host, " /", args.port

    main(host=args.host, port=args.port)
