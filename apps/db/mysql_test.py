import os
import sys
import json
import db_pass #db_pass.py file in the same directory
import pymysql
import datetime



if __name__=="__main__":
    
    jdata = db_pass.login_info
    print (jdata)

    conn = pymysql.connect(host=jdata["db_add"], user=jdata["id"], passwd=jdata["password"], db=jdata["db_name"], port=int(jdata["port"]))

    sql = "INSERT INTO home_co2 (datetime, co2) VALUES (%s, %s)"
    time_now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print (time_now)

    
