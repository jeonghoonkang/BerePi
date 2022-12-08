# -*- coding: utf-8 -*-
#Author : jeonghoonkang, https://github.com/jeonghoonkang

devel_dir="~/devel_opment" #modify on your condition
tmp_dir=devel_dir+"/BerePi/apps"

import datetime
import json
import os
import sys

import db_pass  # db_pass.py file in the same directory
import pymysql

import argparse

def parse_args():
    story = 'read file and put data into MySQL, python driver '
    msg = '\n python {module name}.py  -file {value} -points {value}\n --help for more info'

    parser=argparse.ArgumentParser(description=story, usage=msg, formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument("-file", default='./input.log', help="file which will be read to MySQL DB")
    parser.add_argument("-points", default=1, help="number of points which will be inserted to MySQL DB")
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

def read_log_file(file_name):
    v = None
    t = None
    
    return v, t


def db_insert_from_log(table_name, file_name):
    __val, __time = read_log_file(file_name)

    return None

if __name__=="__main__":
    
    print ("Path")
    print (tmp_dir)
    table_name = "home_co2"
    __r = parse_args()
    print (__r)

    # log file to read
    __file = __r.log_file

    db_insert_from_log(table_name, __file)

# Path: BerePi/apps/db/mysql_read_into.py
