#### RaspberryPi GIO performance
  - http://codeandlife.com/2012/07/03/benchmarking-raspberry-pi-gpio-speed/

#### installation
  - git clone git://git.drogon.net/wiringPi
  - and ./build 
  - compile option needs -lwiringPi
  - see in the ../wiringPi/Makefile
  
#### check PINOUTs in BASH
  - gpio -v
  - gpio readall 
    - it shows all the PINOUTs map table

#### some reference from http://wiringpi.com/reference
Note: Even if you are not using any of the input/output functions you still need to call one of the wiringPi setup functions – just use wiringPiSetupSys() if you don’t need root access in your program and remember to #include <wiringPi.h>

unsigned int millis (void)
This returns a number representing the number of milliseconds since your program called one of the wiringPiSetup functions. It returns an unsigned 32-bit number which wraps after 49 days.

unsigned int micros (void)
This returns a number representing the number of microseconds since your program called one of the wiringPiSetup functions. It returns an unsigned 32-bit number which wraps after approximately 71 minutes.

void delay (unsigned int howLong)
This causes program execution to pause for at least howLong milliseconds. Due to the multi-tasking nature of Linux it could be longer. Note that the maximum delay is an unsigned 32-bit integer or approximately 49 days.

void delayMicroseconds (unsigned int howLong)
