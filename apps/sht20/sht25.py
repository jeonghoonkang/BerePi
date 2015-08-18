
# Author : Philman Jeong (ipmstyle@gmail.com)

import smbus
import time

SHT20_ADDR = 0x40       # SHT20 register address
#SHT20_CMD_R_T = 0xE3   # hold Master Mode (Temperature)
#SHT20_CMD_R_RH = 0xE5  # hold Master Mode (Humidity)
SHT20_CMD_R_T = 0xF3    # no hold Master Mode (Temperature)
SHT20_CMD_R_RH = 0xF5   # no hold Master Mode (Humidity)
#SHT20_WRITE_REG = 0xE6 # write user register 
#SHT20_READ_REG = 0xE7  # read user register 
SHT20_CMD_RESET = 0xFE  # soft reset

bus = smbus.SMBus(1)    # 0 = /dev/i2c-0 (port I2C0), 1 = /dev/i2c-1 (port I2C1)

def reading(v):
    '''try: 
        bus.write_quick(SHT20_ADDR)
    except:
        return False
    '''
    try:
        if v == 1:
            bus.write_byte(SHT20_ADDR, SHT20_CMD_R_T)
        elif v == 2:
            bus.write_byte(SHT20_ADDR, SHT20_CMD_R_RH) 
        else:
          return False
    except:
        return False
        
    time.sleep(.2)
    
    try:
        b = (bus.read_byte(SHT20_ADDR)<<8)
        b += bus.read_byte(SHT20_ADDR)
        b &= 0xFFFC
    except:
        print "I2C read Exception"
        return False
    if v == 1:
        print " binary value : ", bin(b)
        print " dec. value : ", int(b)
    return b

# based on SHT25 Data sheet, Version 3 _ May 2014 
# http://www.sensirion.com/fileadmin/user_upload/customers/sensirion/Dokumente/Humidity/Sensirion_Humidity_SHT25_Datasheet_V3.pdf
# http://www.sensirion.com/fileadmin/user_upload/customers/sensirion/Dokumente/Humidity/Sensirion_Humidity_SHT20_Datasheet_V3.pdf

def calc(temp, humi):
    tmp_temp = 175.72 * float(temp) / pow(2,16) - 46.85
    tmp_humi = 125 * float(humi) / pow(2,16) - 6

    return tmp_temp, tmp_humi

def getTemperature():
    ret = reading(1)
    Temperature = calc(ret,ret)
    if not ret:
        print "I2C problem report"
        return -100
    return Temperature[0]

def getHumidity():
    ret = reading(2)
    Humi = calc(ret,ret)
    if not ret:
        print "I2C problem report"
        return -100
    return Humi[1]

if __name__== "__main__" :

    while True:
        temp = reading(1)
        humi = reading(2)
        if not temp or not humi:
            print "register reading error"
            break
        value = calc(temp, humi)
        print "temp : %s\thumi : %s" % (value[0], value[1])
        time.sleep(4)

