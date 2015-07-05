#!/usr/bin/python
# Author : ipmstyle, https://github.com/ipmstyle
#        : jeonghoonkang, https://github.com/jeonghoonkang

# for the detail of HW connection, see lcd_connect.py

import RPi.GPIO as GPIO
import time, os
from subprocess import *
from lcd_connect import * 

# Define some device constants
LCD_WIDTH = 16    # Maximum characters per line
LCD_CHR = True
LCD_CMD = False

LCD_LINE_1 = 0x80 # LCD RAM address for the 1st line
LCD_LINE_2 = 0xC0 # LCD RAM address for the 2nd line

# Timing constants
E_PULSE = 0.0005
E_DELAY = 0.0005

def lcd_init():

  GPIO.setmode(GPIO.BCM)       # Use BCM GPIO numbers
  GPIO.setup(LCD_E, GPIO.OUT)  # E
  GPIO.setup(LCD_RS, GPIO.OUT) # RS
  GPIO.setup(LCD_D4, GPIO.OUT) # DB4
  GPIO.setup(LCD_D5, GPIO.OUT) # DB5
  GPIO.setup(LCD_D6, GPIO.OUT) # DB6
  GPIO.setup(LCD_D7, GPIO.OUT) # DB7
  #GPIO.setup(LED_ON, GPIO.OUT) # Backlight enable
  GPIO.setup(LCD_RED, GPIO.OUT) # RED Backlight enable
  GPIO.setup(LCD_GREEN, GPIO.OUT) # GREEN Backlight enable
  GPIO.setup(LCD_BLUE, GPIO.OUT) # BLUEBacklight enable

  # Initialise display
  lcd_byte(0x33,LCD_CMD) # 110011 Initialise
  lcd_byte(0x32,LCD_CMD) # 110010 Initialise
  lcd_byte(0x06,LCD_CMD) # 000110 Cursor move direction
  lcd_byte(0x0C,LCD_CMD) # 001100 Display On,Cursor Off, Blink Off
  lcd_byte(0x28,LCD_CMD) # 101000 Data length, number of lines, font size
  lcd_byte(0x01,LCD_CMD) # 000001 Clear display
  time.sleep(E_DELAY)

def lcd_clear():
  lcd_byte(0x01,LCD_CMD) # 000001 Clear display
  time.sleep(E_DELAY)

def lcd_byte(bits, mode):
  # Send byte to data pins
  # bits = data
  # mode = True  for character
  #        False for command

  GPIO.output(LCD_RS, mode) # RS

  # High bits
  GPIO.output(LCD_D4, False)
  GPIO.output(LCD_D5, False)
  GPIO.output(LCD_D6, False)
  GPIO.output(LCD_D7, False)
  if bits&0x10==0x10: GPIO.output(LCD_D4, True)
  if bits&0x20==0x20: GPIO.output(LCD_D5, True)
  if bits&0x40==0x40: GPIO.output(LCD_D6, True)
  if bits&0x80==0x80: GPIO.output(LCD_D7, True)

  # Toggle 'Enable' pin
  lcd_toggle_enable()

  # Low bits
  GPIO.output(LCD_D4, False)
  GPIO.output(LCD_D5, False)
  GPIO.output(LCD_D6, False)
  GPIO.output(LCD_D7, False)
  if bits&0x01==0x01: GPIO.output(LCD_D4, True)
  if bits&0x02==0x02: GPIO.output(LCD_D5, True)
  if bits&0x04==0x04: GPIO.output(LCD_D6, True)
  if bits&0x08==0x08: GPIO.output(LCD_D7, True)

  # Toggle 'Enable' pin
  lcd_toggle_enable()

def lcd_toggle_enable():
  # Toggle enable
  time.sleep(E_DELAY)
  GPIO.output(LCD_E, True)
  time.sleep(E_PULSE)
  GPIO.output(LCD_E, False)
  time.sleep(E_DELAY)

def lcd_string(message,line,style):
  # Send string to display
  # style=1 Left justified
  # style=2 Centred
  # style=3 Right justified

  if style==1:
    message = message.ljust(LCD_WIDTH," ")
  elif style==2:
    message = message.center(LCD_WIDTH," ")
  elif style==3:
    message = message.rjust(LCD_WIDTH," ")

  lcd_byte(line, LCD_CMD)

  for i in range(LCD_WIDTH):
    lcd_byte(ord(message[i]),LCD_CHR)

def redLCDon():
  red_backlight(False)

def greenLCDon():
  green_backlight(False)

def blueLCDon():
  blue_backlight(False)

def LCDoff():
  red_backlight(True)
  green_backlight(True)
  blue_backlight(True)

def yellowLCDon():
  GPIO.output(LCD_BLUE, True)
  GPIO.output(LCD_RED, False)
  GPIO.output(LCD_GREEN, False)

def skyeLCDon():
  GPIO.output(LCD_BLUE, True)
  GPIO.output(LCD_RED, False)
  GPIO.output(LCD_GREEN, False)

def pinkLCDon():
  GPIO.output(LCD_GREEN, True)
  GPIO.output(LCD_RED, False)
  GPIO.output(LCD_BLUE, False)

def whiteLCDon():
  GPIO.output(LCD_RED, False)
  GPIO.output(LCD_GREEN, False)
  GPIO.output(LCD_BLUE, False)

def red_backlight(flag):
  # Toggle red-backlight on-off-on
  GPIO.output(LCD_GREEN, True)
  GPIO.output(LCD_BLUE, True)
  GPIO.output(LCD_RED, flag)

def green_backlight(flag):
  # Toggle green-backlight on-off-on
  GPIO.output(LCD_RED, True)
  GPIO.output(LCD_BLUE, True)
  GPIO.output(LCD_GREEN, flag)

def blue_backlight(flag):
  # Toggle blue-backlight on-off-on
  GPIO.output(LCD_RED, True)
  GPIO.output(LCD_GREEN, True)
  GPIO.output(LCD_BLUE, flag)

def run_cmd(cmd):
    p = Popen(cmd, shell=True, stdout=PIPE)
    output = p.communicate()[0]
    return output

def ip_chk():
    cmd = "ip addr show eth0 | grep inet | awk '{print $2}' | cut -d/ -f1"
    ipAddr = run_cmd(cmd)
    return ipAddr

def wip_chk():
    cmd = "ip addr show wlan0 | grep inet | awk '{print $2}' | cut -d/ -f1"
    wipAddr = run_cmd(cmd)
    return wipAddr

def mac_chk():
    cmd = "ifconfig -a | grep ^eth | awk '{print $5}'"
    macAddr = run_cmd(cmd)
    return macAddr

def wmac_chk():
    cmd = "ifconfig -a | grep ^wlan | awk '{print $5}'"
    wmacAddr = run_cmd(cmd)
    return wmacAddr

def stalk_chk():
    cmd = "hostname"
    return run_cmd(cmd)

if __name__ == '__main__':

  try:
    main()
  except KeyboardInterrupt:
    pass
  finally:
    lcd_byte(0x01, LCD_CMD)
    lcd_string("Goodbye!",LCD_LINE_1,2)
    GPIO.cleanup()

def main():
  # Main program block

  lcd_init()
  # Initialise display
  print ip_chk(), wip_chk(), mac_chk(), wmac_chk(), stalk_chk()

  while True:
    lcd_string('IP address ', LCD_LINE_1,1)
    lcd_string('MAC eth0, wlan0',LCD_LINE_2,1)
    blue_backlight(False) #turn on, yellow
    time.sleep(2.5) # 3 second delay

    str = ip_chk()
    str = str[:-1]
    lcd_string('%s ET' %str,LCD_LINE_1,1)
    str = mac_chk()
    str = str[:-1]
    lcd_string('%s' % (str),LCD_LINE_2,1)
    red_backlight(False) #turn on, yellow
    time.sleep(3.5) # 3 second delay

    str = wip_chk()
    str = str[:-1]
    lcd_string('%s WL     ' % (str),LCD_LINE_1,1)
    str = wmac_chk()
    str = str[:-1]
    lcd_string('%s' % (str),LCD_LINE_2,1)
    green_backlight(False) #turn on, yellow
    time.sleep(3.5) # 5 second delay
        
    str = stalk_chk()
    str = str[:-1]
    lcd_string('sTalk Channel' ,LCD_LINE_1,1)
    lcd_string('%s           ' % (str),LCD_LINE_2,1)
    red_backlight(False) #turn on, yellow
    time.sleep(3.5) # 5 second delay
