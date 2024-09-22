# -*- coding: utf-8 -*-
# author : http://github.com/jeonghoonkang
# author : http://github.com/sonnonet

#import HPMA115S0
#import PMS7003
import dust_chk
import time
import serial
#import influx_simple_driver

import sys
sys.path.append("/home/tinyos/devel/BerePi/apps/logger")
import berepi_logger


if __name__=="__main__" :
        
    DB_SERVER_IP_ADD = '***'
    try:
        print("Starting")
        #hpma115S0 = HPMA115S0.HPMA115S0("/dev/ttyAMA0")
        #hpma115S0 = HPMA115S0.HPMA115S0("/dev/serial0")
        while True:
            try:
                dust_v01, dust_v25, dust_v10 = dust_chk.dustget()
                #dust_chk.continuous_dustget()
                berepi_logger.berelog(" PM0.1 Dust %d  ug/m3 " %(dust_v01))
                berepi_logger.berelog(" PM2.5 Dust %d (50 is bad limit) ug/m3 " %(dust_v25))
                berepi_logger.berelog(" PM10 Dust %d (100 is bad limit) ug/m3 " %(dust_v10))
                exit(1)              
                
            except serial.serialutil.SerialException as e: 
                print ("dust PM2.5 exception", __file__)
                print (e)
                time.sleep(3)
                exit(1)
                
        '''라즈베리파이 스트레치 부터는 기존 AMA0 은 BLE로 사용하면서, 디바이스 파일 명칭 바뀜'''
        #hpma115S0.init()
        #hpma115S0.startParticleMeasurement()


#        while True:
#            if (hpma115S0.readParticleMeasurement()):
#                print("PM2.5: %d ug/m3" % (hpma115S0._pm2_5))
#                print("PM10: %d ug/m3" % (hpma115S0._pm10))
#                berepi_logger.berelog(" PM2.5 Dust %d (50 is bad limit) ug/m3 " %(hpma115S0._pm2_5))
#                ret = influx_simple_driver.influx_write(hpma115S0._pm2_5, DB_SERVER_IP_ADD)
#                if ret != True : print ("[problem|influxDB communication]")
#                elif ret == True : # influx DB에 입력후, 제대로 회신되면 종료
#                  print (" Sensor Data got success through DB")
#                  exit(1)
#            time.sleep(4) # Fail 인 경우 4초후에 다시 시도
#
    except KeyboardInterrupt:
        print("program stopped")
