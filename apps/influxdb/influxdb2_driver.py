#Author : github.com/jeonghoonkang


from datetime import datetime
from sqlite3 import Timestamp
import datetime

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# You can generate a Token from the "Tokens Tab" in the UI
token = "CAIjbOjcqkY2pmxomozEUmeMcbxu2G5KzblhLalMS7vExQ=="
org = "c4aeb19a8b4"
bucket = "keti_sw"

client = InfluxDBClient(url="http://:8086", token=token)
write_api = client.write_api(write_options=SYNCHRONOUS)
# after make data ready, call ''' write_api.write(bucket, org, data) '''

def getTSnow():
    dtnow = datetime.datetime.now()
    #print dtnow.strftime('%Y-%m-%dT%H:%M:%S')
    return dtnow.strftime('%Y-%m-%dT%H:%M:%S')

#print(json_msg)

data = "kangtest,lang=python,mach=i5 value=3.11"
#빈칸은 TAG / VALUE / TIMESTAMP 사이만 존재해야 함 

#print (data)
#write_api.write(bucket, org, data)

write_api.write(bucket, org, json_msg)

# tips from 
# https://influxdb-python.readthedocs.io/en/latest/examples.html
# https://github.com/kimsehwan96/influxdb-study-with-python
