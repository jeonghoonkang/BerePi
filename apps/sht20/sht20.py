
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

bus = smbus.SMBus(1)

def reading(v):
    bus.write_quick(SHT20_ADDR)
    if v == 1:
        bus.write_byte(SHT20_ADDR, SHT20_CMD_R_T)
    elif v == 2:
        bus.write_byte(SHT20_ADDR, SHT20_CMD_R_RH)
    else:
        return False
    time.sleep(.1)
    b = (bus.read_byte(SHT20_ADDR)<<8)
    b += bus.read_byte(SHT20_ADDR)
    return b

def calc(temp, humi):
    tmp_temp = -46.85 + 175.72 * float(temp) / pow(2,16)
    tmp_humi = -6 + 125 * float(humi) / pow(2,16)

    return tmp_temp, tmp_humi


if __name__== "__main__" :

    while True:
        temp = reading(1)
        humi = reading(2)
        if not temp or not humi:
            print "register error"
            break
        value = calc(temp, humi)
        print "temp : %s\thumi : %s" % (value[0], value[1])
        time.sleep(1)
