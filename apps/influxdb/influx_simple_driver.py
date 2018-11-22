# -*- coding: utf-8 -*-
# author : http://github.com/jeonghoonkang

import argparse
import datetime
from influxdb import InfluxDBClient

def getTSnow():
    dtnow = datetime.datetime.now()
    #print dtnow.strftime('%Y-%m-%dT%H:%M:%S')
    return dtnow.strftime('%Y-%m-%dT%H:%M:%S')

default_mname = 'sample_data'
dbname = 'kang_test'

write_json = [
    {
        "measurement": default_mname,
        "tags": {
            "host": "test",
            "work": "iot_insert"
        },
        #"time": "2009-11-10T23:00:00Z",
        "time": getTSnow(),
        "fields": {
            "test_val": 7
        }
    }
]

def main(host='localhost', port=8086, measurename = default_mname):
    """Instantiate a connection to the InfluxDB."""
    user = 'root'
    password = 'root'

    dbuser = 'smly'
    dbuser_password = 'my_secret_password'
    query = 'select value from cpu_load_short;'

    client = InfluxDBClient(host, port, None, None, dbname)

    #print("Create database: " + dbname)
    #client.create_database(dbname)

    #print("Create a retention policy")
    #client.create_retention_policy('awesome_policy', '3d', 3, default=True)

    #print("Switch user: " + dbuser)
    #client.switch_user(dbuser, dbuser_password)

    #print("Switch user: " + user)
    #client.switch_user(user, password)

    #print("Drop database: " + dbname)
    #client.drop_database(dbname)


    query = 'show measurements on %s;' %dbname
    print("Querying data: " + query)
    result = client.query(query)
    print("Result: {0}".format(result))
    
    write_json[measurement] = measurename
    print("Write points: {0}".format(write_json))
    client.write_points(write_json)

    query = 'select * from %s ;' %measurename
    print("Querying data: " + query)
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


def influx_write(val, measurename, host='127.0.0.1', port=8086) :
    print "trying to ..."
    print host, port, measurename
    # todo : try 구문 입력 및 에러시 반복 수행 
    main(host, port, val, measurename)    

if __name__ == '__main__':

    args = parse_args()
    #print args
    print "trying to ..."
    print args.host, " /", args.port

    main(host=args.host, port=args.port)
