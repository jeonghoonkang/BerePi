# Simple example of reading the MCP3008 analog input channels and printing
# them all out.
# Author: Tony DiCola
# License: Public Domain
import time
import json
import requests

# Import SPI library (for hardware SPI) and MCP3008 library.
import Adafruit_GPIO.SPI as SPI
import Adafruit_MCP3008
from multiprocessing import Pool, Queue, Manager

# Software SPI configuration:
CLK  = 26
MISO = 19 
MOSI = 13
CS   = 6
mcp = Adafruit_MCP3008.MCP3008(clk=CLK, cs=CS, miso=MISO, mosi=MOSI)

# Hardware SPI configuration:
# SPI_PORT   = 0
# SPI_DEVICE = 0
# mcp = Adafruit_MCP3008.MCP3008(spi=SPI.SpiDev(SPI_PORT, SPI_DEVICE))

# To insert data into TSDB
PUT_PERIOD = 30
PUT_URL = "http://125.140.110.217:4242/api/put"
METRIC_LIST = ["CT000.test1", "CT001.test1", "CT002.test1",
        "CT003.test1", "CT000.cur.test1", "CT001.cur.test1",
        "CT002.cur.test1", "CT003.cur.test1"]
PUT_TAGS = {
        "device": "ct_sensor"
        }

# Period of reading ADC channel values
READ_PERIOD = 0.5


def cal_currentVal(_values):
    current_values = []
    for i in range(4):
        temp = (_values[7] - _values[i]) * 13.765
        current_values.append(temp)
    return current_values

def sendBuf(_session, _url, _buffer):
    headers = {'content-type': 'application/json'}

    for i in xrange(0, len(_buffer), 50):
        response = _session.post(_url, data=json.dumps(_buffer[i:i+50]), headers= headers, timeout=3)
        
        while response.status_code > 204:
            print "error!"
            print response
            response = _session.post(_url, data=json.dumps(_buffer[i:i+50]), headers= headers, timeout=3)


def guarantee_putRetry(_session, _url, _buf, _time=3):
    while(True):
        try:
            sendBuf(_session, _url, _buf)
        except requests.exceptions.ConnectionError:
            time.sleep(_time)
            continue
        except requests.exceptions.Timeout:
            continue
        break

def put_proc(_queue):
    with requests.Session() as s:
        while True:
            buf = []
            timestamp, values, current_values = _queue.get()
            all_values = values + current_values
            for metric, value in zip(METRIC_LIST, all_values):
                dp = dict()
                dp["metric"] = metric
                dp["timestamp"] = int(timestamp)
                dp["value"] = value
                dp["tags"] = PUT_TAGS 
                buf.append(dp)
            guarantee_putRetry(s, PUT_URL, buf)


def main_proc(_queue):
    print('Reading MCP3008 values, press Ctrl-C to quit...')
    # Print nice channel column headers.
    print('| {0:>4} | {1:>4} | {2:>4} | {3:>4} | {4:>4} | {5:>4} | {6:>4} | {7:>4} || {8:>4} | {9:>4} | {10:>4} | {11:>4} |'.format(*(range(8) + range(4))))    
    print('-' * 87)
    # Main program loop.
    cnt = 0
    while True:
        # Read all the ADC channel values in a list.
        values = [0]*8
        timestamp = str(time.time()).split('.')[0]
        for i in range(8):
            # The read_adc function will get the value of the specified channel (0-7).
            values[i] = mcp.read_adc(i)
        # Calculate current value(mA)
        current_values = cal_currentVal(values)
        
        # Insert data into the queue
        if cnt % int(PUT_PERIOD / READ_PERIOD) == 0:
            _queue.put([timestamp, values[:4], current_values])
            cnt = 0

        # Print the ADC values & current value.
        print('ts = %s' %(timestamp),  '| {0:>4} | {1:>4} | {2:>4} | {3:>4} | {4:>4} | {5:>4} | {6:>4} | {7:>4} || {8:>4} | {9:>4} | {10:>4} | {11:>4} |'.format(*(values + current_values)))
        # Pause for half a second.
        time.sleep(READ_PERIOD)
        cnt += 1

if __name__ == '__main__':
    manager = Manager()
    data_queue = manager.Queue()

    pool = Pool(processes=2)
    try:
        mainproc = pool.apply_async(main_proc, [data_queue])
        putproc = pool.apply_async(put_proc, [data_queue])
        
        main_res = mainproc.get(timeout=1e20)
        put_res = putproc.get(timeout=1e20) 
    except KeyboardInterrupt:                                                                                                                                                                                                         
        print "KeyboardInterrupt occured!\n\n" 
        pool.terminate()
    finally:
        pool.close()
        pool.join()
