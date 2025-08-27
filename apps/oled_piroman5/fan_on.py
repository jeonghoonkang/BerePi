#!/usr/bin/env python3
"""Simple helper to activate the CPU cooling fan and its RGB LEDs.

Running this script will turn on the fan connected to BCM pin 18 and
light the two RGB LED outputs on pins 5 and 6. The state persists after
exit so the fan and LEDs stay on.

On startup it reports the current fan status, the level of GPIO 6 and the
current CPU temperature using :mod:`rich` formatting.
"""

import atexit
import os
import argparse

from gpiozero import CPUTemperature, OutputDevice, Device
from rich.console import Console

FAN_PIN = 18
RGBFAN_PIN = (5, 6)


def parse_args():
    """Return parsed command line arguments."""

    parser = argparse.ArgumentParser(
        description="Control the CPU cooling fan and its RGB LEDs",
    )
    parser.add_argument(
        "--state",
        choices=["on", "off"],
        default="on",
        help="desired fan state",
    )
    return parser.parse_args()


def main():
    """Control the CPU fan and RGB LED fan."""

    args = parse_args()
    console = Console()

    # Prevent gpiozero from resetting the pin states on exit so the fan
    # remains running after this script terminates.
    if hasattr(Device, "_shutdown"):
        try:
            atexit.unregister(Device._shutdown)
        except Exception:
            pass

    # Release any previously allocated pins to avoid GPIO busy errors.
    for pin in (FAN_PIN,) + RGBFAN_PIN:
        try:
            Device.pin_factory.release(pin)
        except Exception:
            pass

    # Inspect existing states without changing them
    fan = OutputDevice(FAN_PIN, active_high=True, initial_value=None)
    leds = [OutputDevice(pin, active_high=True, initial_value=None) for pin in RGBFAN_PIN]

    cpu_temp = CPUTemperature().temperature
    fan_state = "ON" if fan.is_active else "OFF"
    gpio6_state = "HIGH" if leds[1].is_active else "LOW"

    console.print(f"[bold]CPU fan:[/bold] {fan_state}")
    console.print(f"[bold]GPIO 6:[/bold] {gpio6_state}")
    console.print(f"[bold]CPU temp:[/bold] {cpu_temp:.1f}\N{DEGREE SIGN}C")
    console.print(f"[bold]Requested state:[/bold] {args.state.upper()}")

<<<<<<< HEAD
    # Apply requested state
    if args.state == "on":
        fan.on()
        for led in leds:
            led.on()
    else:
        fan.off()
        for led in leds:
            led.off()
=======
    fan = cpu_fan_on()
    led = led_fan_on()

    fan.on()

    while(1):
      time.sleep(60)
>>>>>>> 63862c8e (fix)


if __name__ == "__main__":
    main()
    # Exit immediately to avoid any library clean-up resetting the pins
    os._exit(0)
