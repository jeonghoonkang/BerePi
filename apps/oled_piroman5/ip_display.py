#!/usr/bin/env python3
"""Display current IP address on OLED using piroman5 driver."""

import time
import subprocess

# piroman5 OLED driver, built on luma.oled
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageFont
import gpiod

# pin used to control the cooling fan on piroman5 max
FAN_PIN = 18


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
    chip = gpiod.Chip("gpiochip0")
    line = chip.get_line(FAN_PIN)
    line.request(consumer="ip_display", type=gpiod.LINE_REQ_DIR_OUT, default_vals=[1])


    # Initialize OLED display via I2C
    serial = i2c(port=1, address=0x3C)
    device = ssd1306(serial)

    font = ImageFont.load_default()


    try:
        while True:
            ip = get_ip_address("eth0")
            with canvas(device) as draw:
                draw.text((0, 0), "IP Address", font=font, fill=255)
                draw.text((0, 16), ip, font=font, fill=255)
            time.sleep(3)
    finally:

      line.set_value(0)
        line.release()
        chip.close()



if __name__ == "__main__":
    main()
