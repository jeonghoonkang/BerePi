
// Author : jeonghoon.kang@gmail.com

#include <wiringPi.h>
#include <stdio.h>

int pin_num = 25;

void light_on(){
    digitalWrite (pin_num, HIGH);
    return void;
}

int main (void) {
    unsigned int end, start = 0;
    unsigned int delayOn = 280;   //micro-sec
    unsigned int delayStay = 40;   //micro-sec
    unsigned int delayOff = 9680;   //micro-sec

    wiringPiSetup () ;
    pinMode (pin_num, OUTPUT) ;

    for (;;) {
        digitalWrite (pin_num, HIGH);
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
0.009680 , keep turn-off LED
One Cycle is 10 msec
*/
