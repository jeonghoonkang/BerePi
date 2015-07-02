#!/usr/bin/python
# Author : ipmstyle, https://github.com/ipmstyle
#        : jeonghoonkang, https://github.com/jeonghoonkang

# The wiring for the LCD is as follows:
# 1 : GND
# 2 : 5V
# 3 : Contrast (0-5V)* - GND connect
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
# 15: LCD Backlight +5V** - 5V connect
# 16: RED LCD Backlight (-)
# 17: GREEN LCD Backlight (-)
# 18: BLUE LCD Backlight (-)

# Define GPIO to LCD mapping, Raspi pin mapping
LCD_RS = 6 # LCD pin 4 : RS (Register Select)
LCD_E  = 13 # LCD pin 6 : Enable or Strobe
LCD_D4 = 19 # LCD pin 11: Data Bit 4
LCD_D5 = 26 # LCD pin 12: Data Bit 5
LCD_D6 = 21 # LCD pin 13: Data Bit 6
LCD_D7 = 20 # LCD pin 14: Data Bit 7
#LED_ON = 4
LCD_RED = 16 # LCD pin 16: RED LCD Backlight (-)
LCD_GREEN = 12 # LCD pin 17: GREEN LCD Backlight (-)
LCD_BLUE = 7 # # LCD pin 18: BLUE LCD Backlight (-)
