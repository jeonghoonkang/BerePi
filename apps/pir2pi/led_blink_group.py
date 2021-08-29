
import time
import lgpio

#17: location 11 Header pin
#27: location 13 Header pin
#22: location 15 Header pin

#group_claim_output	Claims a group of GPIO for outputs
#gpio_claim_output	Claims a GPIO for output
#group_claim_output(handle, gpio, levels=[0], lFlags=0)
#group_write(handle, gpio, group_bits, group_mask=GROUP_ALL)
#gpio_write(handle, gpio, level)

LED0 = 17
LED1 = 27
LED2 = 22
LEDS = [17, 27, 22]

if __name__=="__main__":

    print ("...Start...")

    # open the gpio chip and set the LED pin as output
    handle = lgpio.gpiochip_open(0)
    print (' return ', lgpio.group_claim_output(handle, LEDS, [1,1,1]), ' (note) 0 is good working')
    #lgpio.gpio_claim_output(h, LED1)
    #lgpio.gpio_claim_output(h, LED2)

    try:
        # Turn the GPIO pin low
        lgpio.group_write(handle, 17, 0x6, 0x7) # 3개 on, blue, green, red
        #lgpio.group_write(handle, 17, 0x4, 0x7) # 2개 on,       green, red
        #lgpio.group_write(handle, 17, 0x2, 0x7) # 2개on, blue, red, A
        #lgpio.group_write(handle, 17, 0x0, 0x7) # 1개on, red 0,8
        #lgpio.group_write(handle, 17, 0xa, 0x7) # no on 5,1,3,9
        print ('GIO', 'is On')
        time.sleep(5)

        # Turn the GPIO pin high
        lgpio.group_write(handle, 17, 0x7, 0x7)
        #lgpio.group_write(handle, LEDS, 0x000008)
        #lgpio.gpio_write(h, LED0, 1)
        #lgpio.gpio_write(h, LED1, 1)
        #lgpio.gpio_write(h, LED2, 1)
        print ('GIO', 'is Off') #LED 보드 구현에 따라, H->On, L->On 이 다를수 있음
        time.sleep(2)

        lgpio.gpiochip_close(handle)


    except KeyboardInterrupt:
        lgpio.gpio_write(handle, LED0, 0)
        lgpio.gpio_write(handle, LED1, 0)
        lgpio.gpio_write(handle, LED2, 0)
        lgpio.gpiochip_close(h)

