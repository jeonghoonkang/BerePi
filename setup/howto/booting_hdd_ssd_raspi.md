

https://m.blog.naver.com/emperonics/221979352174


https://www.raspberrypi.org/documentation/hardware/raspberrypi/bcm2711_bootloader_config.md


sudo rpi-eeprom-update

sudo rpi-eeprom-update -a

BOOT_ORDER=0xf41

sudo -E rpi-eeprom-config --edit

vcgencmd bootloader_config

