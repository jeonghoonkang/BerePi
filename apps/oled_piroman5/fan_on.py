#!/usr/bin/env python3
"""Simple helper to activate the CPU cooling fan and its RGB LEDs.

Running this script will turn on the fan connected to BCM pin 18 and
light the two RGB LED outputs on pins 5 and 6. The state persists after
exit so the fan and LEDs stay on.
"""

import atexit

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
    """Turn on the CPU fan and RGB LED fan."""

    if hasattr(Device, "_shutdown"):
        try:
            atexit.unregister(Device._shutdown)
        except Exception:
            pass
    cpu_fan_on()
    led_fan_on()



if __name__ == "__main__":
    main()
