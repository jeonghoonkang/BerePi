## This code for LED BD 00

import serial,os,time
import sys
import RPi.GPIO as GPIO

# RASPI2 PIN OUT NUMBER
# check pin location, http.............
bled = 16
gled = 20
rled = 21

# HW setup, GPIO
GPIO.cleanup()
GPIO.setmode(GPIO.BCM)
GPIO.setup(bled, GPIO.OUT)
GPIO.setup(gled, GPIO.OUT)
GPIO.setup(rled, GPIO.OUT)
GPIO.output(bled, True) # ON first time
GPIO.output(gled, True) # ON first time
GPIO.output(rled, True) # ON first time
time.sleep(1)


def ledb_on():
    GPIO.output(bled, True)

def ledg_on():
    GPIO.output(gled, True)

def ledr_on():
    GPIO.output(rled, True)

def ledb_off():
    GPIO.output(bled, False)

def ledg_off():
    GPIO.output(gled, False)

def ledr_off():
    GPIO.output(rled, False)

def ledall_off():
    GPIO.output(bled, False)
    GPIO.output(gled, False)
    GPIO.output(rled, False)

led_time_idx = 0

while True:
    led_time_idx += 1
    if ((led_time_idx % 3) == 0) :
        ledall_off()
        ledb_on()

    elif ((led_time_idx % 3) == 1) :
        ledall_off()
        ledg_on()

    elif ((led_time_idx % 3) ==  2) :
        ledall_off()
        ledr_on()

    time.sleep(0.3)

GPIO.cleanup()
