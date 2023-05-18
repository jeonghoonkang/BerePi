
## for RaspberryPi-4

sudo rpi-eeprom-update

sudo rpi-eeprom-update -a

BOOT_ORDER=0xf41


sudo -E rpi-eeprom-config --edit

 vcgencmd bootloader_config
