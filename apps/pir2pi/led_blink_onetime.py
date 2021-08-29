import time
import lgpio

#17: location 11 Header pin
#27: location 13 Header pin
#22: location 15 Header pin

LED0 = 17
LED1 = 27
LED2 = 22

if __name__=="__main__":

    print ("...Start...")

    # open the gpio chip and set the LED pin as output
    h = lgpio.gpiochip_open(0)
    print (lgpio.gpio_claim_output(h, LED0))
    lgpio.gpio_claim_output(h, LED1)
    lgpio.gpio_claim_output(h, LED2)

    try:

        while True:
            # Turn the GPIO pin low
            lgpio.gpio_write(h, LED0, 0)
            lgpio.gpio_write(h, LED1, 0)
            lgpio.gpio_write(h, LED2, 0)
            print ('GIO', 'is On')
            time.sleep(90)

            # Turn the GPIO pin high
            lgpio.gpio_write(h, LED0, 1)
            lgpio.gpio_write(h, LED1, 1)
            lgpio.gpio_write(h, LED2, 1)
            print ('GIO', 'is Off') #LED 보드 구현에 따라, H->On, L->On 이 다를수 있음
            time.sleep(1)


    except KeyboardInterrupt:
        lgpio.gpio_write(h, LED0, 1)
        lgpio.gpio_write(h, LED1, 1)
        lgpio.gpio_write(h, LED2, 1)
        lgpio.gpiochip_close(h)

