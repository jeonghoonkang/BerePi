# code from http://www.emsystech.de/raspi-sht21
# Author http://github.com/jeonghoonkang

import fcntl
import time
import unittest

class SHT25:

    # control constants on I2C bus for SHT25
    _SOFTRESET = 0xFE
    _I2C_ADDRESS = 0x40
    _TRIGGER_TEMPERATURE_NO_HOLD = 0xF3
    _TRIGGER_HUMIDITY_NO_HOLD = 0xF5
    _STATUS_BITS_MASK = 0xFFFC

    # From: /linux/i2c-dev.h
    I2C_SLAVE = 0x0703
    I2C_SLAVE_FORCE = 0x0706

    # datasheet (v4), page 9, table 7
    # for suggesting the use of these better values
    # code copied from https://github.com/mmilata/growd
    _TEMPERATURE_WAIT_TIME = 0.086  # (datasheet: typ=66, max=85)
    _HUMIDITY_WAIT_TIME = 0.030     # (datasheet: typ=22, max=29)

    def __init__(self, device_number=1):
        self.i2c = open('/dev/i2c-%s' % device_number, 'r+', 0)
        fcntl.ioctl(self.i2c, self.I2C_SLAVE, 0x40)
        self.i2c.write(chr(self._SOFTRESET))
        time.sleep(0.050)

    def read_temperature(self):    
        self.i2c.write(chr(self._TRIGGER_TEMPERATURE_NO_HOLD))
        time.sleep(self._TEMPERATURE_WAIT_TIME)
        data = self.i2c.read(3)
        if self._calculate_checksum(data, 2) == ord(data[2]):
            return self._get_temperature_from_buffer(data)

    def read_humidity(self):    
        self.i2c.write(chr(self._TRIGGER_HUMIDITY_NO_HOLD))
        time.sleep(self._HUMIDITY_WAIT_TIME)
        data = self.i2c.read(3)
        if self._calculate_checksum(data, 2) == ord(data[2]):
            return self._get_humidity_from_buffer(data)

    def close(self):
        self.i2c.close()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    @staticmethod
    def _calculate_checksum(data, number_of_bytes):
        # CRC
        POLYNOMIAL = 0x131  # //P(x)=x^8+x^5+x^4+1 = 100110001
        crc = 0
        # calculates 8-Bit checksum with given polynomial
        for byteCtr in range(number_of_bytes):
            crc ^= (ord(data[byteCtr]))
            for bit in range(8, 0, -1):
                if crc & 0x80:
                    crc = (crc << 1) ^ POLYNOMIAL
                else:
                    crc = (crc << 1)
        return crc

    @staticmethod
    def _get_temperature_from_buffer(data):
        unadjusted = (ord(data[0]) << 8) + ord(data[1])
        unadjusted &= SHT25._STATUS_BITS_MASK  # zero the status bits
        unadjusted *= 175.72
        unadjusted /= 1 << 16  # divide by 2^16
        unadjusted -= 46.85
        return unadjusted

    @staticmethod
    def _get_humidity_from_buffer(data):
        unadjusted = (ord(data[0]) << 8) + ord(data[1])
        unadjusted &= SHT25._STATUS_BITS_MASK  # zero the status bits
        unadjusted *= 125.0
        unadjusted /= 1 << 16  # divide by 2^16
        unadjusted -= 6
        return unadjusted

def getTemperature():
    try:
        with SHT25(1) as sht25:
            ret = sht25.read_temperature()
    except:
        print "Exception : SHT25 Instance init - I2C I/O"
        return -100
        pass
    print "Temperature: %s" % ret
    return ret

def getHumidity():
    try:
        with SHT25(1) as sht25:
          ret = sht25.read_humidity()
    except:
        print "Exception : SHT25 Instance init - I2C I/O"
        return -100
    print "Humidity: %s" % ret
    return ret

if __name__ == "__main__":
    try:
        while True:
            with SHT25(1) as sht25:
                print "Temperature: %s" % sht25.read_temperature()
                print "Humidity   : %s" % sht25.read_humidity()
            time.sleep(1.5)
    except IOError, e:
        print e
        print "Error creating connection to i2c.  This must be run as root"
