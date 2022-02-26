# jeonghoonkang

# http://www.eltsensor.co.kr/products-by-gas/co2/ndir/monitor?tpf=product/view&category_code=101012&code=22

import serial

if __name__ == "__main__":
    
    op = serial.Serial('/dev/ttyUSB0', baudrate=38400, rtscts=True)
    in_string = op.read(32)
    
    ppm = find_ppm(in_string)
    
    pass2file(ppm)
    
