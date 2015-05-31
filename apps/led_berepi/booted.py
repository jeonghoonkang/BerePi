## This code for HW init
## It will show LED Blue ON, 30secs after booting
## We can easily check the booting has problem

import sys
sys.path.append("../leds")
from ledinit import *

debug_print = 0

def BootLed():
	ledb_on()
	time.sleep(1)
	ledb_off()
	time.sleep(1)

if __name__== "__main__" :
    if debug_print is 1: print "(booted.py) >> Starting "
    while True:
        BootLed()
        if debug_print is 1: print "(booted.py) >> end of a loop"
    GPIO.cleanup()
