
#include <wiringPi.h>
int main (void) {
    unsigned int end, start = 0;
    int pin_num = 25;
    wiringPiSetup () ;
    pinMode (pin_num, OUTPUT) ;

    for (;;) {
        digitalWrite (pin_num, HIGH) ;
        start = micros();
        delayMicroseconds (50);
        end = micros();
        printf("u-sec : %d",end-start);
        digitalWrite (pin_num,  LOW) ;
        delay (50) ;
    }
    return 0 ;
}

