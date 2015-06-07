
// Author : jeonghoon.kang@gmail.com


#include <wiringPi.h>
#include <stdio.h>

int main (void) {
    unsigned int end, start = 0;
    unsigned int udelaytime = 3000;
    int pin_num = 25;

    wiringPiSetup () ;
    pinMode (pin_num, OUTPUT) ;

    for (;;) {
        digitalWrite (pin_num, HIGH) ;
        start = micros();
        delayMicroseconds (udelaytime);
        end = micros();
        printf("start= %d \n",start);
        printf("endt= %d \n",end);
        printf("u-sec : %d / target %d usec \n",end-start, udelaytime);
        digitalWrite (pin_num,  LOW) ;
        delay (500) ;
    }
    return 0 ;
}

/* dust sensor timing
0.000280 , wait until init and turn on LED in the sensor, read ADC
0.000040 , after 40 usec, turn off LED
0.009680 , keep off
One Cycle is 10 msec
*/
