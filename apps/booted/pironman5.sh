#!/bin/bash

# NOTE: `gpioset`/`gpioget` generally need root privileges to access
# `/dev/gpiochip*`. To run this script as a normal user, grant access via
# a `gpio` group or capabilities. For example:
#   sudo usermod -aG gpio "$USER"
#   echo 'SUBSYSTEM=="gpio",KERNEL=="gpiochip*",GROUP="gpio",MODE="0660"' | \
#       sudo tee /etc/udev/rules.d/60-gpio.rules
#   sudo udevadm control --reload-rules && sudo udevadm trigger
# or
#   sudo setcap 'cap_sys_rawio+ep' $(command -v gpioset) $(command -v gpioget)

#CASE FAN (LED FAN)
#output GPIO6 = 1
echo -n "chang output, current="
gpioget gpiochip4 6

gpioset gpiochip4 6=1

echo -n " pin status GPIO6 >> " 
gpioget gpiochip4 6
