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

    table_name = "home_co2"

    sql = "INSERT INTO " + table_name + " (datetime, co2) VALUES (%s, %s)"
    time_now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print (time_now)



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


