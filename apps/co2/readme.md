
##### Intro
  - Author : jeonghoon.kang@gmail.com
  - Please check source code : **co2_t110.py**, it is simple and easy code.
  - also read the log.file.txt and print_out_msg.txt which are output of code. 
  
##### CO2 sensor reading on RaspberryPi2
  1. CO2 sensor reading
    - HW : Serial interface 
    - SW : Python 
  2. Local log file
    - Python logging module
  1. Remote DB insert support via webservice
    - RESTful API, using PUT
    - Python "requests" module

##### Hardware
  - (HW ver.01) Photo, CO2 sensor and 3 LEDs - **https://goo.gl/NhEfXZ**
  - CO2 module will be update second week of June, it will be directly connected to Raspi2 pinout like LEDs PCB in the photo above. 

##### CO2 sensor specification, datasheet
  1. T110 3.3V 
     - http://eltsensor.co.kr/2012/eng/product/co2-sensor-module-T110-3V.html
     - http://eltsensor.co.kr/2012/eng/pdf/T-110/DS_T-110-3V_ver1.210.pdf
  1. RaspberryPi Pin out
     - http://www.raspberrypi-spy.co.uk/2012/06/simple-guide-to-the-rpi-gpio-header-and-pins
     
