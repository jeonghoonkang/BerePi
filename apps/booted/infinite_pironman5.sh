#!/bin/bash

gpioset --mode=exit gpiochip4  5=1

# make output GPIO6 = 1
gpioset --mode=signal gpiochip4  6=1

