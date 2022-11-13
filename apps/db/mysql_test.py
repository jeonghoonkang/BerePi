# -*- coding: utf-8 -*-
#Author : jeonghoonkang, https://github.com/jeonghoonkang

devel_dir="~/devel_opment"
tmp_dir=devel_dir+"/BerePi/apps"

import datetime
import json
import os
import sys

import db_pass  # db_pass.py file in the same directory
import pymysql

import argparse

def parse_args():
    story = 'MySQL driver of Python '
    msg = '\n python {module name}.py  -data {value} \n --help for more info'

    '''
    usg = '\n python tsdb_read.py  -url x.x.x.x \
        -port 4242 -start 2016110100 -end 2016110222 \
        -rdm metric_name, -wm write_metric_name -tags="{id:911}" --help for more info'

	parser.add_argument("-url",    default="127.0.0.1",
	    help="URL input, or run fails")
    parser.add_argument("-start",  default='2016070100',
        help="start time input, like 2016110100")
    parser.add_argument("-port",   default=4242,
        help="port input, like 4242")
    parser.add_argument("-wtm", default='__keti_test__',
        help="write-metric ")
    parser.add_argument("-tags", default="{'sensor':'_test_sensor_', 'desc':'_test_'}", help="tags ")
    '''
    parser=argparse.ArgumentParser(description=story, usage=msg, formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument("-data", default=1, help="value which will be inserted to MySQL DB")
    args = parser.parse_args()
    return args

def db_insert(table_name, in_data):

    jdata = db_pass.login_info
    print ( "...using db info. ==> ", jdata)
    t_now = datetime.datetime.now()
    t_date = t_now.strftime("%Y-%m-%d %H:%M:%S")
    db_ins_date = str(t_date)
    #db insert date type ==> str(t_date)

    args = (t_date, in_data)
    sql = "INSERT INTO " + table_name + " (datetime, co2) VALUES (%s, %s)"
    print (db_ins_date, in_data)
	

    try:
        conn = pymysql.connect(host=jdata["db_add"], user=jdata["id"], passwd=jdata["password"], db=jdata["db_name"], port=int(jdata["port"]))
		#conn = MySQLdb.connect( host=hostname, user=username, passwd=password, db=database )
        cursor = conn.cursor()
        cursor.execute(sql, args)
        conn.commit()

    except Exception as error:
        print("Error: {}".format(error))

    finally:
        cursor.close()
        conn.close()


def db_read(table_name, cnt=1):

    jdata = db_pass.login_info
    try:
        conn = pymysql.connect(host=jdata["db_add"], user=jdata["id"], passwd=jdata["password"], db=jdata["db_name"], port=int(jdata["port"]))

        select_sql = "SELECT * FROM " + table_name + " ORDER by datetime DESC LIMIT " + str(cnt) 
        cursor = conn.cursor()
        cursor.execute(select_sql)
        ret = cursor.fetchall()
    except Exception as error:
        print("Error: {}".format(error))

    print (" reading data from DB ")
    print (ret)
    return ret 



if __name__=="__main__":
    
    table_name = "home_co2"
    __r = parse_args()
    print (__r)
    val = __r.data

    db_insert(table_name, val)
    db_read(table_name, 5)

	

'''
# Routine to insert temperature records into the pidata.temps table:
def insert_record( device, datetime, temp, hum ):
	query = "INSERT INTO temps3 (device,datetime,temp,hum) VALUES (%s,%s,%s,%s)"
    	args = (device,datetime,temp,hum)

    	try:
        	conn = MySQLdb.connect( host=hostname, user=username, passwd=password, db=database )
		cursor = conn.cursor()
        	cursor.execute(query, args)
		conn.commit()

    	except Exception as error:
        	print(error)

    	finally:
        	cursor.close()
        	conn.close()

# Print welcome 
print('[{0:s}] starting on {1:s}...'.format(prog_name, datetime.datetime.today().strftime('%Y-%m-%d %H:%M:%S')))

# Main loop
try:
	while True:
		hum, temp = Adafruit_DHT.read_retry(dht_sensor_type, dht_sensor_port)
		temp = temp * 9/5.0 + 32
		now = datetime.datetime.now()
		date = now.strftime('%Y-%m-%d %H:%M:%S')
		insert_record(device,str(date),format(temp,'.2f'),format(hum,'.2f'))
		time.sleep(180)
		
except (IOError,TypeError) as e:
	print("Exiting...")

except KeyboardInterrupt:  
    	# here you put any code you want to run before the program   
    	# exits when you press CTRL+C  
	print("Stopping...")

finally:
	print("Cleaning up...")  
	GPIO.cleanup() # this ensures a clean exit
'''


