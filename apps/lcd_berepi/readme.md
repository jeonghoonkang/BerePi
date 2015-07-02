 - Introduciton
   - Raspi LCD driver
   - It shows IP address, stalk channel 
 - How to run the code
   - **sudo python OOO.py**
 - Run result
  - ![LCD running !](raspi_lcd_color.jpg)


Wiring info

| LCD pin | Function | RPi GPIO |
|---|---|---|
|01 |GND |GND |
|02 |+5V |+5V |
|03 |Contrast |GND |
|04 |RS |GPIO 27 |
|05 |RW |GND |
|06 |E |GPIO 22 |
|07 |Data 0 | |
|08 |Data 1 | |
|09 |Data 2 | |
|10 |Data 3 | |
|11 |Data 4 |GPIO 25 |
|12 |Data 5 |GPIO 24 |
|13 |Data 6 |GPIO 23 |
|14 |Data 7 |GPIO 18 |
|15 |+5V |+5V |
|16 |-R/red |GPIO 4 |
|17 |-G/green |GPIO 17 |
|18 |-B/blue |GPIO 7 |
