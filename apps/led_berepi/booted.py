## This code for HW init
## It will show LED Blue ON, 30secs after booting
## We can easily check the booting has problem

thispath='...BerePi/trunk/apps/led_berepi'

import sys
from ledinit import *

debug_print = 1

def BootLed():
	ledb_on()
	time.sleep(1)
	ledb_off()
	time.sleep(1)

if __name__== "__main__" :
    if debug_print is 1: print "(%s/booted.py) >> Starting " %thispath
    while True:
        BootLed()
        if debug_print is 1: print "(%s/booted.py) >> end of a loop" %thispath
    GPIO.cleanup()
