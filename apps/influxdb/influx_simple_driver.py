
# -*- coding: utf-8 -*-
# author : http://github.com/jeonghoonkang

import argparse
import datetime
from influxdb import InfluxDBClient

def getTSnow():
    dtnow = datetime.datetime.now()
    #print dtnow.strftime('%Y-%m-%dT%H:%M:%S')
    return dtnow.strftime('%Y-%m-%dT%H:%M:%S')


def main(host='localhost', port=8086):
    """Instantiate a connection to the InfluxDB."""
    user = 'root'
    password = 'root'
    dbname = 'kang_test'
    measurementname = 'sample_data'
    dbuser = 'smly'
    dbuser_password = 'my_secret_password'
    query = 'select value from cpu_load_short;'

    json_body = [
        {
            "measurement": measurementname,
            "tags": {
                "host": "test",
                "work": "iot_insert"
            },
            #"time": "2009-11-10T23:00:00Z",
            "time": getTSnow(),
            "fields": {
                "Float_value": 0.64,
                "Int_value": 3,
                "String_value": "Text",
                "Bool_value": True
            }
        }
    ]

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

    print("Write points: {0}".format(json_body))
    client.write_points(json_body)

    query = 'select * from %s ;' %measurementname
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


if __name__ == '__main__':
    args = parse_args()
    #print args
    main(host=args.host, port=args.port)
