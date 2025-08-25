#!/usr/bin/env python3
"""Display IP address and time on the OLED using the piroman5 driver.

This script is designed to be called from ``cron`` once every two minutes.
It updates the OLED with the current IPv4 address and timestamp, and
controls the cooling fan on the piroman5 max board. By default the
fan runs continuously, but a different duty cycle (e.g. 75 or 50) may
be specified via ``--fan-duty`` to run the fan only for part of the
two-minute interval when the CPU temperature is below ``50°C``.

Dependencies can be installed with::

    pip3 install -r requirements.txt
"""

from datetime import datetime
import subprocess
import argparse

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
RGBFAN_PIN = (5, 6)
# RGB LED pins for the fan lighting
RGB_PINS = (4, 17, 7)
# temperature threshold in Celsius for turning the fan on
TEMP_THRESHOLD = 47.0


def get_ip_address(interface="eth0"):
    """Return the IPv4 address for a network interface."""
    cmd = ["ip", "addr", "show", interface]
    output = subprocess.check_output(cmd, encoding="utf-8")
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("inet "):
            return line.split()[1].split("/")[0]
    return "0.0.0.0"


def parse_args():
    """Return parsed command line arguments."""

    parser = argparse.ArgumentParser(
        description="Update the OLED and control the cooling fan once."
    )
    parser.add_argument(
        "--fan-duty",
        type=int,
        default=100,
        help=(
            "Percentage of the two-minute cycle to run the fan when the CPU "
            "temperature is below the threshold (0-100)."
        ),
    )
    return parser.parse_args()


def main():
    """Update the OLED and control the cooling fan once."""

    args = parse_args()
    args.fan_duty = max(0, min(args.fan_duty, 100))

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

    except Exception:
        # On older pin factories ``release`` may not exist
        pass


    fan = OutputDevice(FAN_PIN, active_high=True)
    rgb_leds = [OutputDevice(pin, active_high=True) for pin in RGBFAN_PIN]
    rgb_leds[0].on()
    rgb_leds[1].on()
    cpu = CPUTemperature()
    console = Console()



    # Determine IP address once; update other values in the loop
    ip = get_ip_address("eth0")

    total_runtime = 120
    fan_on_duration = total_runtime * args.fan_duty / 100
    remaining = total_runtime

    # Initialize OLED display via I2C
    serial = i2c(port=1, address=0x3C)
    device = ssd1306(serial)
    font = ImageFont.load_default()

    while remaining >= 0:
        temp = cpu.temperature
        if temp >= TEMP_THRESHOLD or remaining > total_runtime - fan_on_duration:
            fan.on()
        else:
            fan.off()
        fan_status = "ON" if fan.is_active else "OFF"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with canvas(device) as draw:
            draw.text((0, 0), ip, font=font, fill=255)
            draw.text((0, 16), now, font=font, fill=255)
            draw.text((0, 32), f"CPU {temp:.1f}C F:{fan_status}", font=font, fill=255)
            draw.text(
                (0, 48),
                f"Duty: {args.fan_duty}%/{int(total_runtime)}s L{int(remaining)}s",
                font=font,
                fill=255,
            )
        console.print(
            f"OLED display 중입니다... 남은 시간: {remaining}초 | "
            f"CPU: {temp:.1f}°C | Fan: {fan_status}   ",
            end="\r",
        )
        if remaining == 0:
            break
        time.sleep(5)
        remaining -= 5
    console.print()

if __name__ == "__main__":
    main()
