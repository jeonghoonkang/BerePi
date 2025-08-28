#!/usr/bin/env python4
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
import time

from gpiozero import CPUTemperature, OutputDevice, Device
from rich.console import Console

FAN_PIN = 18



from gpiozero import DigitalInputDevice
from time import sleep

# FAN LED는 GPIO 6번에 연결되어 있습니다.
RGBFAN_LED_PIN = 6

# GPIO 6번 핀을 입력 장치로 설정합니다.
# 풀업 저항을 활성화하여 핀이 연결되지 않은 상태(HIGH)를 방지합니다.
# pull_up=False는 기본 상태를 LOW로 설정하여 실제 신호를 정확히 감지합니다.
led_pin = DigitalInputDevice(RGBFAN_LED_PIN, pull_up=False)



#    time.sleep(5) # 잠시 대기하여 안정된 값을 읽습니다.

#    leds = [OutputDevice(pin, active_high=True, initial_value=None) for pin in RGBFAN_PIN]

if led_pin.is_active:
  print("GPIO 6 is currently HIGH.")
else:
  print("GPIO 6 is currently LOW.")


