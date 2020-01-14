#!/usr/bin/python3

import sys
import board
import neopixel
import argparse
import time

# cmd set
# line 1/2 : 12, 18
# on (white : 255,255,255)
# off (0,0,0)
# color (R,G,B)
#####
# sudo pip3 install adafruit-circuitpython-neopixel
# led_strip.py <ID> <cmd> <option>
# led_strip.py 1 on
# led_strip.py 1 off
# led_strip.py 1 color 255 255 255

def led_on(pin):
    if pin == 1:
        pixels = neopixel.NeoPixel(board.D12, 20)
    elif pin == 2:
        pixels = neopixel.NeoPixel(board.D18, 20)
    else:
        print("wrong id")
        return False
    pixels.fill((255, 255, 255))
    return True

def led_off(pin):
    if pin == 1:
        pixels = neopixel.NeoPixel(board.D12, 20)
    elif pin == 2:
        pixels = neopixel.NeoPixel(board.D18, 20)
    else:
        return False
    pixels.fill((0, 0, 0))
    return True

def led_color(pin, R=255,G=255,B=255):
    if pin == 1:
        pixels = neopixel.NeoPixel(board.D12, 20)
    elif pin == 2:
        pixels = neopixel.NeoPixel(board.D18, 20)
    else:
        return False
    pixels.fill((R, G, B))
    return True

def main():
    parser = argparse.ArgumentParser(description="control 2-LED strips")
    parser.add_argument('-c', '--cmd', dest='cmd')

    pass

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[2] == 'on':
        led_on(int(sys.argv[1]))
    elif len(sys.argv) == 3 and sys.argv[2] == 'off':
        led_off(int(sys.argv[1]))
    elif len(sys.argv) == 6 and sys.argv[2] == 'color':
        led_color(int(sys.argv[1]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]))
    else:
        print("wrong argv")
