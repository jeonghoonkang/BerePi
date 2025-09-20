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
import serial
import sys
import time
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
from serial.tools import list_ports


BNAME = Path("/home/tinyos/devel_opment")
LOG_DIR = str(BNAME / "BerePi/apps/logger")

sys.path.append(LOG_DIR)

import berepi_logger


def _configure_berepi_logger_fallback():
    """Ensure berepi_logger uses the fallback log path when needed."""

    primary_base = Path("/home/tinyos/devel")
    if primary_base.exists():
        return

    fallback_log_path = Path("/home/tinyos/devel_opment/BerePi/logs/berelogger.log")
    fallback_log_path.parent.mkdir(parents=True, exist_ok=True)

    if getattr(berepi_logger, "LOG_FILENAME", "") == str(fallback_log_path):
        return

    for handler in list(berepi_logger.logger.handlers):
        berepi_logger.logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    handler = RotatingFileHandler(
        str(fallback_log_path), mode="a", maxBytes=200000, backupCount=9
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
    )
    berepi_logger.logger.addHandler(handler)
    berepi_logger.LOG_FILENAME = str(fallback_log_path)


_configure_berepi_logger_fallback()

# piroman5 OLED driver, built on luma.oled
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageFont
import atexit
from gpiozero import OutputDevice, CPUTemperature, Device
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


def find_ppm(ins):
    print("RAW string", ins)
    stnum = 0
    if ins[0] == 0xF1 and ins[1] == 0xF2 and ins[2] == 0x02:
        stnum = ins[3] * 256 + ins[4]
    else:
        print("error in data")
        return None
    ret = stnum
    print("...", stnum, "ppm")
    return ret


def pass2file(ins):
    print("...logging...")
    print(time.strftime("%Y-%m-%d %H:%M"))
    logclass = berepi_logger.selfdatalogger()
    logclass.set_logger("CO2_POC")
    logclass.berelog("co2 ppm", str(ins), "CO2_POC ")
    print("co2 ppm", str(ins), "CO2_POC ")


def read_co2(op):
    rq_str = b"\xF1\xF2\x01\x1C"
    op.write(rq_str)
    in_string = op.read(size=8)
    ppm = find_ppm(in_string)
    if ppm is None:
        in_string = op.read(size=8)
        ppm = find_ppm(in_string)
    return ppm


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


    fan = cpu_fan_on()
    rgb_leds = led_fan_on()

    cpu = CPUTemperature()
    console = Console()
    try:
        co2_port = serial.Serial("/dev/ttyUSB0", baudrate=9600, rtscts=True)
        time.sleep(3)
    except Exception:
        co2_port = None

    co2_port = None
    try:
        ports = [p.device for p in list_ports.comports()]
        console.print(
            "Connected USB ports: " + (", ".join(ports) if ports else "None")
        )
        port_name = "/dev/ttyUSB0"
        if port_name not in ports and ports:
            port_name = ports[0]
        if port_name in ports:
            console.print(f"Using CO2 sensor port: {port_name}")
            co2_port = serial.Serial(port_name, baudrate=9600, rtscts=True)
            time.sleep(3)
    except Exception as exc:
        console.print(f"CO2 sensor setup failed: {exc}")



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
        co2_ppm = None
        if co2_port:
            try:
                co2_ppm = read_co2(co2_port)
                if co2_ppm is not None:
                    pass2file(co2_ppm)
            except Exception:
                co2_ppm = None
        co2_text = f"CO2 {co2_ppm}ppm" if co2_ppm is not None else "CO2 N/A"
        with canvas(device) as draw:
            draw.text((0, 0), ip, font=font, fill=255)
            draw.text((0, 12), now, font=font, fill=255)
            draw.text((0, 24), f"CPU {temp:.1f}C F:{fan_status}", font=font, fill=255)
            draw.text((0, 36), co2_text, font=font, fill=255)

            draw.text(
                (0, 48),
                f"Duty: {args.fan_duty}%/{int(total_runtime)}s L{int(remaining)}s",
                font=font,
                fill=255,
            )
        console.log(
            f"OLED display 중입니다... 남은 시간: {remaining}초 | "
            f"CPU: {temp:.1f}°C | CO2: {co2_ppm if co2_ppm is not None else 'N/A'}ppm | Fan: {fan_status}"

        )
        if remaining == 0:
            break
        time.sleep(5)
        remaining -= 5

    if co2_port:
        co2_port.close()

if __name__ == "__main__":
    main()
