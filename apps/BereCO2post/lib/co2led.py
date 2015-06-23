## This code for LEDs on T110 BereCO2

thispath='...BerePi/apps/BereCO2post/lib/'

import time
import sys
import RPi.GPIO as GPIO

debug_print = 0
# if LED PCB has GND pcb_GND = 1, otherwise 0
# hsetting : it is HW setting, you should check it
pcb_GND = 1

# important, sensorname shuould be pre-defined, unique sensorname
bdname = "BereCO2.led"

# hsetting : it is HW setting, you should check it
bled = 17
gled = 22
rled = 27

def linit():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(bled, GPIO.OUT)
    GPIO.setup(gled, GPIO.OUT)
    GPIO.setup(rled, GPIO.OUT)

# below assuming that you are using LEDs PCB board with GND
def ledblue_on(): 
    linit()
    if (pcb_GND is 1) : 
        GPIO.output(bled, True) 
    else : 
        GPIO.output(bled, False)

def ledgreen_on():
    linit()
    if pcb_GND is 1 :
   	    GPIO.output(gled, True)
    else :
   	    GPIO.output(gled, False)

def ledred_on():
    linit()
    if pcb_GND is 1 :
	    GPIO.output(rled, True)
    else :
   	    GPIO.output(rled, False)

def ledbluegreen_on():
    linit()
    if pcb_GND is 1 :
	    GPIO.output(bled, True)
	    GPIO.output(gled, True)
    else :
   	    GPIO.output(bled, False)
   	    GPIO.output(gled, False)

def ledyellow_on():
    linit()
    if pcb_GND is 1 :
	    GPIO.output(rled, True)
	    GPIO.output(gled, True)
    else :
   	    GPIO.output(rled, False)
   	    GPIO.output(gled, False)

def ledpurple_on():
    linit()
    if pcb_GND is 1 :
	    GPIO.output(rled, True)
	    GPIO.output(bled, True)
    else :
   	    GPIO.output(rled, False)
   	    GPIO.output(bled, False)
def ledwhite_on():
    linit()
    if pcb_GND is 1 :
	    GPIO.output(bled, True)
	    GPIO.output(gled, True)
	    GPIO.output(rled, True)
    else :
   	    GPIO.output(bled, False)
   	    GPIO.output(gled, False)
   	    GPIO.output(rled, False)

def ledblue_off():
    linit()
    if pcb_GND is 1 :
   	    GPIO.output(bled, False)
    else :
   	    GPIO.output(bled, True)
def ledgreen_off():
    linit()
    if pcb_GND is 1 :
   	    GPIO.output(gled, False)
    else :
   	    GPIO.output(gled, True)
def ledred_off():
    linit()
    if pcb_GND is 1 :
   	    GPIO.output(rled, False)
    else : 
        GPIO.output(rled, True)

def ledall_off():
    ledblue_off()
    ledgreen_off()
    ledred_off()

def ledall_on():
    ledblue_on()
    ledgreen_on()
    ledred_on()

def ledinit() :
    # HW setup, GPIO
    linit()
    ledall_on()
    time.sleep(0.3)
    ledall_off()
    # please check the HW connection between LEDs and CPU
    # if you using GND on the LED HW, GPIO.output(bled, True) will show LED ON

ledinit()

if __name__== "__main__" :
    print ">> Starting init"
    init()
    print ">> end of init"
    while True:
        ledb_on()
        ledg_on()
        ledr_on()
        time.sleep(2)
        ledb_off()
        ledg_off()
        ledr_off()
        time.sleep(2)
    GPIO.cleanup()
