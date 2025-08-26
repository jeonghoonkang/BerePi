#!/usr/bin/env python3
"""Simple helper to activate the CPU cooling fan and its RGB LEDs.

Running this script will turn on the fan connected to BCM pin 18 and
light the two RGB LED outputs on pins 5 and 6. The state persists after
exit so the fan and LEDs stay on.
"""

import atexit
import time
from gpiozero import OutputDevice, Device

FAN_PIN = 18
RGBFAN_PIN = (5, 6)

def cpu_fan_on(pin=FAN_PIN):
    """Activate the CPU cooling fan and return its device."""
    fan = OutputDevice(pin, active_high=True)
    fan.on()
    return fan


def led_fan_on(pins=RGBFAN_PIN):
    """Activate the LED fan outputs and return their devices."""
    leds = [OutputDevice(pin, active_high=True) for pin in pins]
    for led in leds:
        led.on()
    return leds


def main():

    # Prevent gpiozero from resetting the pin states on exit so the fan
    # remains in the state we set. Older versions of gpiozero may not
    # expose ``Device._shutdown``, so handle that case gracefully.
    if hasattr(Device, "_shutdown"):
        try:
            atexit.unregister(Device._shutdown)
        except Exception:
            pass

    # Release previously allocated pins to avoid lgpio "GPIO busy" errors
    try:
        Device.pin_factory.release(FAN_PIN)
        Device.pin_factory.release(RGBFAN_PIN)

    except Exception:
        # On older pin factories ``release`` may not exist
        pass



    fan = cpu_fan_on()
    led = led_fan_on()

    fan.on()

    time.sleep(60)


if __name__ == "__main__":
    main()
