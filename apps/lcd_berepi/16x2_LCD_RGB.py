#!/usr/bin/python
# Author : ipmstyle, https://github.com/ipmstyle

# The wiring for the LCD is as follows:
# 1 : GND
# 2 : 5V
# 3 : Contrast (0-5V)*
# 4 : RS (Register Select)
# 5 : R/W (Read Write)       - GROUND THIS PIN
# 6 : Enable or Strobe
# 7 : Data Bit 0             - NOT USED
# 8 : Data Bit 1             - NOT USED
# 9 : Data Bit 2             - NOT USED
# 10: Data Bit 3             - NOT USED
# 11: Data Bit 4
# 12: Data Bit 5
# 13: Data Bit 6
# 14: Data Bit 7
# 15: LCD Backlight +5V**
# 16: RED LCD Backlight (-)
# 17: GREEN LCD Backlight (-)
# 18: BLUE LCD Backlight (-)

import RPi.GPIO as GPIO
import time

# Define GPIO to LCD mapping
LCD_RS = 27
LCD_E  = 22
LCD_D4 = 25
LCD_D5 = 24
LCD_D6 = 23
LCD_D7 = 18
#LED_ON = 4
LCD_RED = 4
LCD_GREEN = 17
LCD_BLUE = 7

# Define some device constants
LCD_WIDTH = 16    # Maximum characters per line
LCD_CHR = True
LCD_CMD = False

LCD_LINE_1 = 0x80 # LCD RAM address for the 1st line
LCD_LINE_2 = 0xC0 # LCD RAM address for the 2nd line

# Timing constants
E_PULSE = 0.0005
E_DELAY = 0.0005

def main():
  # Main program block

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
  lcd_init()

  # Toggle backlight on-off-on
  red_backlight(True)
  time.sleep(1)
  red_backlight(False)
  time.sleep(1)

  green_backlight(True)
  time.sleep(1)
  green_backlight(False)
  time.sleep(1)

  blue_backlight(True)
  time.sleep(1)
  blue_backlight(False)
  time.sleep(1)


  while True:
    red_backlight(True)
    lcd_string("Rasbperry Pi",LCD_LINE_1,2)
    lcd_string(": RED",LCD_LINE_2,2)

    time.sleep(3) # 3 second delay
    red_backlight(False)
    time.sleep(.5)
    
    green_backlight(True)
    lcd_string("Rasbperry Pi",LCD_LINE_1,2)
    lcd_string(": GREEN",LCD_LINE_2,2)

    time.sleep(3) # 3 second delay
    green_backlight(False)

    time.sleep(.5)
    
    blue_backlight(True)
    lcd_string("Rasbperry Pi",LCD_LINE_1,2)
    lcd_string(": BLUE",LCD_LINE_2,2)

    time.sleep(3) # 3 second delay
    blue_backlight(False)
    time.sleep(.5)

    """
    #- RED +  GREEN
    red_backlight(True)
    green_backlight(True)
    lcd_string("RED",LCD_LINE_1,2)
    lcd_string("GREEN",LCD_LINE_2,2)
    time.sleep(3)
    green_backlight(False)
    red_backlight(False)
    time.sleep(0.5)
    #- BLUE +  GREEN
    blue_backlight(True)
    green_backlight(True)
    lcd_string("BLUE",LCD_LINE_1,2)
    lcd_string("GREEN",LCD_LINE_2,2)
    time.sleep(3)
    green_backlight(False)
    blue_backlight(False)

    #- RED + BLUE
    red_backlight(True)
    blue_backlight(True)
    lcd_string("RED",LCD_LINE_1,2)
    lcd_string("BLUE",LCD_LINE_2,2)
    time.sleep(3)
    blue_backlight(False)
    red_backlight(False)

    #- RED + GREEN + BLUE
    red_backlight(True)
    blue_backlight(True)
    green_backlight(True)
    lcd_string("RED, BLUE",LCD_LINE_1,2)
    lcd_string("GREEN",LCD_LINE_2,2)
    time.sleep(3)

    red_backlight(False)
    blue_backlight(False)
    green_backlight(False)

    time.sleep(5)
    """

def lcd_init():
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
  if bits&0x10==0x10:
    GPIO.output(LCD_D4, True)
  if bits&0x20==0x20:
    GPIO.output(LCD_D5, True)
  if bits&0x40==0x40:
    GPIO.output(LCD_D6, True)
  if bits&0x80==0x80:
    GPIO.output(LCD_D7, True)

  # Toggle 'Enable' pin
  lcd_toggle_enable()

  # Low bits
  GPIO.output(LCD_D4, False)
  GPIO.output(LCD_D5, False)
  GPIO.output(LCD_D6, False)
  GPIO.output(LCD_D7, False)
  if bits&0x01==0x01:
    GPIO.output(LCD_D4, True)
  if bits&0x02==0x02:
    GPIO.output(LCD_D5, True)
  if bits&0x04==0x04:
    GPIO.output(LCD_D6, True)
  if bits&0x08==0x08:
    GPIO.output(LCD_D7, True)

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

#def lcd_backlight(flag):
#  # Toggle backlight on-off-on
#  GPIO.output(LED_ON, flag)

def red_backlight(flag):
  # Toggle red-backlight on-off-on
  GPIO.output(LCD_RED, flag)

def green_backlight(flag):
  # Toggle green-backlight on-off-on
  GPIO.output(LCD_GREEN, flag)

def blue_backlight(flag):
  # Toggle blue-backlight on-off-on
  GPIO.output(LCD_BLUE, flag)

if __name__ == '__main__':

  try:
    main()
  except KeyboardInterrupt:
    pass
  finally:
    lcd_byte(0x01, LCD_CMD)
    lcd_string("Goodbye!",LCD_LINE_1,2)
    GPIO.cleanup()
