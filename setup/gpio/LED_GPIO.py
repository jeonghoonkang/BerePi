import time
import lgpio

#17,27,22

LED = 27

# open the gpio chip and set the LED pin as output
h = lgpio.gpiochip_open(0)
lgpio.gpio_claim_output(h, LED)

try:
    while True:
        # Turn the GPIO pin high
        lgpio.gpio_write(h, LED, 1)
<<<<<<< HEAD
        print ('GIO', LED, 'is Off') #LED 보드 구현에 따라, H->On, L->On 이 다를수 있음
        time.sleep(1)
=======
        print ('GIO', LED, 'is On') 
        time.sleep(3)
>>>>>>> 76f1ffaf (blink)

        # Turn the GPIO pin low
        lgpio.gpio_write(h, LED, 0)
<<<<<<< HEAD
        print ('GIO', LED, 'is On')
        time.sleep(3)

=======
        print ('GIO', LED, 'is Off') 
        time.sleep(1)
        
>>>>>>> 76f1ffaf (blink)
except KeyboardInterrupt:
    lgpio.gpio_write(h, LED, 0)
    lgpio.gpiochip_close(h)


