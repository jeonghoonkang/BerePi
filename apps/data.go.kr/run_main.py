# -*- coding: utf-8 -*-
# author : http://github.com/jeonghoonkang

import time
import get_public_micro_particle
import influx_simple_driver

if __name__=="__main__" :
        
    try:
        print(" Loop Starting")

        while True:
            publicdata = get_public_micro_particle.get_public_mise()
            public_val = publicdata[3]
            ret = influx_simple_driver.influx_write(public_val, 'public_dust', '127.0.0.1')
                  #def influx_write(val, mname=None, host='127.0.0.1',  port=8086) 

            if ret != True : print "[problem|influx]"
            time.sleep(300)

    except KeyboardInterrupt:
        print("program stopped")
