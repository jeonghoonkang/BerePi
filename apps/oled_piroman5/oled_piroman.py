#!/usr/bin/env python3
"""Display system information on the OLED without controlling the fan."""

from datetime import datetime
import subprocess
import serial
import sys
import time
from serial.tools import list_ports

BNAME = "/home/tinyos/devel_opment/"
LOG_DIR = BNAME + "selfcloud/apps/log"

sys.path.append(LOG_DIR)

import berepi_logger

from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageFont
from gpiozero import CPUTemperature
from rich.console import Console


def get_ip_address(interface="eth0"):
    """Return the IPv4 address for a network interface."""
    cmd = ["ip", "addr", "show", interface]
    output = subprocess.check_output(cmd, encoding="utf-8")
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("inet "):
            return line.split()[1].split("/")[0]
    return "0.0.0.0"


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


def main():
    console = Console()
    cpu = CPUTemperature()
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

    ip = get_ip_address("eth0")
    total_runtime = 120
    remaining = total_runtime

    serial_intf = i2c(port=1, address=0x3C)
    device = ssd1306(serial_intf)
    font = ImageFont.load_default()

    while remaining >= 0:
        temp = cpu.temperature
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
            draw.text((0, 24), f"CPU {temp:.1f}C", font=font, fill=255)
            draw.text((0, 36), co2_text, font=font, fill=255)
            draw.text((0, 48), f"L{int(remaining)}s", font=font, fill=255)
        console.log(
            f"OLED display 중입니다... 남은 시간: {remaining}초 | "
            f"CPU: {temp:.1f}°C | CO2: {co2_ppm if co2_ppm is not None else 'N/A'}ppm"
        )
        if remaining == 0:
            break
        time.sleep(5)
        remaining -= 5
    if co2_port:
        co2_port.close()


if __name__ == "__main__":
    main()
