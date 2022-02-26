# jeonghoonkang

# http://www.eltsensor.co.kr/products-by-gas/co2/ndir/monitor?tpf=product/view&category_code=101012&code=22

import serial
import time

def find_ppm(ins):
    print ('RAW string',ins)
    ix = ins.find(10) #find '/n' 
    #print ('ix', ix, type(ix), ins[ix:ix+1])

    multi = 0
    loop = 0
    stnum = 0

    for ch in ins[ix+1:ix+7]:
        #print (ch) #check if ASCII code
        loop += 1
        multi = int (1000000 / (10**loop))
        #print (multi)
        if (ch != 32): #find not space character
            stnum += ((ch-48) * multi)

    ret = stnum
    print ('...', stnum, 'ppm') #ppm print
    return ret


def pass2file(ins):
    print("...logging...")

if __name__ == "__main__":
    
    op = serial.Serial('/dev/ttyUSB0', baudrate=38400, rtscts=True)
    time.sleep(3) 

    in_string = op.read(32)
   
    ppm = find_ppm(in_string)
    
    pass2file(ppm)

    exit(__file__ + " all done...")
    
