
## RaspberryPi 4 까지 적용, NVME RaspberryPi5 는 아래 링크로 이동하세요.



https://m.blog.naver.com/emperonics/221979352174
https://www.raspberrypi.org/documentation/hardware/raspberrypi/bcm2711_bootloader_config.md


### 라즈베리파이4 확인 방법
- 업데이트
  - sudo rpi-eeprom-update
  - sudo rpi-eeprom-update -a

- 부팅 순서 변경
  - sudo -E rpi-eeprom-config --edit
  - BOOT_ORDER=0xf41
    - 0xf14 로 저장되어 있음. 이경우 변경해야 함
    - NVME, Rpi5 인 경우는, F416 => (참조) setup/raspi5/readme.md

- 확인 방법
  - vcgencmd bootloader_config



### 라즈베리파이3 확인 방법 
참고 : https://m.blog.naver.com/jeonsr8710/221783418217

```pi@raspberrypi:~ $ vcgencmd otp_dump | grep 17```

```17:3020000a (USB부팅) 1020000a는 USB부팅이 안되는 설정임```

- 설정방법 
<pre>
#!/bin/bash 
pi@raspberrypi:~ $ echo program_usb_boot_mode=1 | sudo tee -a /boot/config.txt﻿
</pre>
