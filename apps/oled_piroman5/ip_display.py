#!/usr/bin/env python3
"""Display IP address and time on the OLED using the piroman5 driver.

This script is designed to be called from ``cron`` once per minute.
It updates the OLED with the current IPv4 address and timestamp, and
controls the cooling fan on the piroman5 max board when the CPU
temperature exceeds ``55°C``.

Dependencies can be installed with::

    pip3 install -r requirements.txt
"""

from datetime import datetime
import subprocess

# piroman5 OLED driver, built on luma.oled
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageFont
import atexit
from gpiozero import OutputDevice, CPUTemperature, Device
import time
from rich.console import Console

# pin used to control the cooling fan on piroman5 max
FAN_PIN = 18
# RGB LED pins for the fan lighting
RGB_PINS = (4, 17, 7)
# temperature threshold in Celsius for turning the fan on
TEMP_THRESHOLD = 55.0


def get_ip_address(interface="eth0"):
    """Return the IPv4 address for a network interface."""
    cmd = ["ip", "addr", "show", interface]
    output = subprocess.check_output(cmd, encoding="utf-8")
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("inet "):
            return line.split()[1].split("/")[0]
    return "0.0.0.0"


def main():
    """Update the OLED and control the cooling fan once."""

    # Prevent gpiozero from resetting the pin states on exit so the fan
    # remains in the state we set. Older versions of gpiozero may not
    # expose ``Device._shutdown``, so handle that case gracefully.
    if hasattr(Device, "_shutdown"):
        try:
            atexit.unregister(Device._shutdown)
        except Exception:
            pass


    fan = OutputDevice(FAN_PIN, active_high=True)
    rgb_leds = [OutputDevice(pin, active_high=True) for pin in RGB_PINS]
    cpu = CPUTemperature()
    console = Console()

    def update_rgb_fan(temp: float) -> str:
        """Update RGB LED fan based on CPU temperature."""
        if temp <= 45.0:
            status = "1LED"
            rgb_leds[0].on()
            for led in rgb_leds[1:]:
                led.off()
        else:
            status = "ON"
            for led in rgb_leds:
                led.on()
        return status

    # Determine IP address and current time
    ip = get_ip_address("eth0")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    temp = cpu.temperature
    if temp >= TEMP_THRESHOLD:
        fan.on()
    else:
        fan.off()
    rgb_status = update_rgb_fan(temp)
    fan_status = "ON" if fan.is_active else "OFF"

    # Initialize OLED display via I2C
    serial = i2c(port=1, address=0x3C)
    device = ssd1306(serial)

    font = ImageFont.load_default()

    # Draw the information once. The display retains the last frame so
    # the text remains visible after the program ends.
    with canvas(device) as draw:
        draw.text((0, 0), ip, font=font, fill=255)
        draw.text((0, 16), now, font=font, fill=255)
        draw.text((0, 32), f"CPU {temp:.1f}C F:{fan_status}", font=font, fill=255)
        draw.text((0, 48), f"RGB {rgb_status}", font=font, fill=255)

    for sec in range(5, 0, -1):
        console.print(
            f"OLED display 중입니다... 남은 시간: {sec}초   ",
            style="bold green",
            end="\r",
        )
        time.sleep(1)
    console.print(end="\r")

    remaining = 60
    while remaining >= 0:
        temp = cpu.temperature
        if temp >= TEMP_THRESHOLD:
            fan.on()
        else:
            fan.off()
        rgb_status = update_rgb_fan(temp)
        fan_status = "ON" if fan.is_active else "OFF"
        console.print(
            f"OLED display 중입니다... 남은 시간: {remaining}초 | "
            f"CPU: {temp:.1f}°C | Fan: {fan_status} | RGB: {rgb_status}   ",
            end="\r",
        )
        if remaining == 0:
            break
        time.sleep(10)
        remaining -= 10
    console.print()

if __name__ == "__main__":
    main()
