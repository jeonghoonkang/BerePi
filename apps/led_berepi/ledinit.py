## This code for LED BD 00

thispath='...raspi/hwlib/leds/'

import time
import sys
import RPi.GPIO as GPIO

debug_print = 0
# if LED PCB has GND pcb_GND = 1, otherwise 0
# hsetting : it is HW setting, you should check it
pcb_GND = 1

# important, sensorname shuould be pre-defined, unique sensorname
bdname = "led.00"

# hsetting : it is HW setting, you should check it
bled = 16
gled = 20
rled = 21


# below assuming that you are using LEDs PCB board with GND
def ledb_on(): 
    if (pcb_GND is 1) : 
        GPIO.output(bled, True) 
    else : 
        GPIO.output(bled, False)

def ledg_on():
	if pcb_GND is 1 :
   	    GPIO.output(gled, True)
	else :
   	    GPIO.output(gled, False)

def ledr_on():
	if pcb_GND is 1 :
	    GPIO.output(rled, True)
	else :
   	    GPIO.output(rled, False)

def ledb_off():
	if pcb_GND is 1 :
   	    GPIO.output(bled, False)
	else :
   	    GPIO.output(bled, True)
def ledg_off():
	if pcb_GND is 1 :
   	    GPIO.output(gled, False)
	else :
   	    GPIO.output(gled, True)
def ledr_off():
    if pcb_GND is 1 :
   	    GPIO.output(rled, False)
    else : 
        GPIO.output(rled, True)

def ledall_off():
    ledb_off()
    ledg_off()
    ledr_off()

def ledall_on():
    ledb_on()
    ledg_on()
    ledr_on()

def init() :
    # HW setup, GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(bled, GPIO.OUT)
    GPIO.setup(gled, GPIO.OUT)
    GPIO.setup(rled, GPIO.OUT)
    ledall_on()
    time.sleep(0.3)
    ledall_off()
    # please check the HW connection between LEDs and CPU
    # if you using GND on the LED HW, GPIO.output(bled, True) will show LED ON

init()

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
