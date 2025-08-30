#!/bin/bash

#CASE FAN (LED FAN)
#output GPIO6 = 1  
echo -n "chang output, current="
gpioget gpiochip4 6

gpioset gpiochip4 6=1 

echo -n " pin status GPIO6 >> " 
gpioget gpiochip4 6
