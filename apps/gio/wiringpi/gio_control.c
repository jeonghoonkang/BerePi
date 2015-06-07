
#include <wiringPi.h>
int main (void)
{
      wiringPiSetup () ;
        pinMode (25, OUTPUT) ;
          for (;;)
                {
                        digitalWrite (0, HIGH) ;
                            delay (500) ;
                                digitalWrite (0,  LOW) ;
                                    delay (500) ;
                                      }
            return 0 ;
}

