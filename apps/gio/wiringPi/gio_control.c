
#include <wiringPi.h>
int main (void) {
    int pin_num = 25;
    wiringPiSetup () ;
    pinMode (pin_num, OUTPUT) ;

    for (;;) {
        digitalWrite (pin_num, HIGH) ;
        delayMicroseconds (50000) ;
        digitalWrite (pin_num,  LOW) ;
        delay (50) ;
    }
    return 0 ;
}

