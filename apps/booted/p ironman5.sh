#!/bin/bash

#CASE FAN (LED FAN)
#output GPIO6 = 1  
gpioinfo gpiochip4
gpioget gpiochip4 6
echo "chang output"
gpioset gpiochip4 6=1 
gpioget gpiochip4 6
gpioinfo gpiochip4
