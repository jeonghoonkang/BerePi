## This code for LED BD 00

import serial,os,time
import sys
import RPi.GPIO as GPIO

# RASPI2 PIN OUT NUMBER
# check pin location, http.............
b0led = 16
g0led = 20
r0led = 21

b1led = 26
g1led = 19
r1led = 13

# HW setup, GPIO
GPIO.cleanup()
GPIO.setmode(GPIO.BCM)
GPIO.setup(b0led, GPIO.OUT)
GPIO.setup(g0led, GPIO.OUT)
GPIO.setup(r0led, GPIO.OUT)
GPIO.setup(b1led, GPIO.OUT)
GPIO.setup(g1led, GPIO.OUT)
GPIO.setup(r1led, GPIO.OUT)
GPIO.output(b0led, True) # ON first time
GPIO.output(g0led, True) # ON first time
GPIO.output(r0led, True) # ON first time
GPIO.output(b1led, True) # ON first time
GPIO.output(g1led, True) # ON first time
GPIO.output(r1led, True) # ON first time
time.sleep(1)


def ledb0_on():
    GPIO.output(b0led, True)

def ledg0_on():
    GPIO.output(g0led, True)

def ledr0_on():
    GPIO.output(r0led, True)

def ledb0_off():
    GPIO.output(b0led, False)

def ledg0_off():
    GPIO.output(g0led, False)

def ledr0_off():
    GPIO.output(r0led, False)

def ledb1_on():
    GPIO.output(b1led, True)

def ledg1_on():
    GPIO.output(g1led, True)

def ledr1_on():
    GPIO.output(r1led, True)

def ledb1_off():
    GPIO.output(b1led, False)

def ledg1_off():
    GPIO.output(g1led, False)

def ledr1_off():
    GPIO.output(r1led, False)

def ledall_off():
    GPIO.output(b0led, False)
    GPIO.output(g0led, False)
    GPIO.output(r0led, False)
    GPIO.output(b1led, False)
    GPIO.output(g1led, False)
    GPIO.output(r1led, False)

led_time_idx = 0

while True:
    led_time_idx += 1
    if ((led_time_idx % 3) == 0) :
        ledall_off()
        ledb0_on()
        ledb1_on()

    elif ((led_time_idx % 3) == 1) :
        ledall_off()
        ledg0_on()
        ledg1_on()

    elif ((led_time_idx % 3) ==  2) :
        ledall_off()
        ledr0_on()
        ledr1_on()

    time.sleep(0.3)

GPIO.cleanup()
