#!/usr/bin/env python3
"""Display IP address and time on the OLED using the piroman5 driver.

This script is designed to be called from ``cron`` once per minute.
It updates the OLED with the current IPv4 address and timestamp, and
controls the cooling fan on the piroman5 max board when the CPU
temperature exceeds ``55°C``.

Dependencies can be installed with::
=======
"""Display current IP address on OLED using piroman5 driver.

Requirements installed with::

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

# pin used to control the cooling fan on piroman5 max
FAN_PIN = 18
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
    # remains in the state we set.
    atexit.unregister(Device._shutdown)

    fan = OutputDevice(FAN_PIN, active_high=True)
    cpu = CPUTemperature()

    # Determine IP address and current time
    ip = get_ip_address("eth0")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if cpu.temperature >= TEMP_THRESHOLD:
        fan.on()
    else:
        fan.off()

    # Initialize OLED display via I2C
    serial = i2c(port=1, address=0x3C)
    device = ssd1306(serial)

    font = ImageFont.load_default()

    # Draw the information once. The display retains the last frame so
    # the text remains visible after the program ends.
    with canvas(device) as draw:
        draw.text((0, 0), ip, font=font, fill=255)
        draw.text((0, 16), now, font=font, fill=255)
if __name__ == "__main__":
    main()
