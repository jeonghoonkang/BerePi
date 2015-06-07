
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

