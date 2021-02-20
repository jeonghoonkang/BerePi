#  Display rotate (HDMI)
- dispaly_rotate=3 (1~4, clock wise prgress)
- /boot/config.txt

# Serial Port
- RaspberryPi3 에서는 UART 사용방법이 변경됨
  - sudo raspi-config Interface Serial 에서 콘솔출력 No, 시리얼 enable Yes 해주어야 함
  - BT와 UART0이 공유되고 있기 때문에, disable후, 시리얼 사용해야함
  - RPI 시리얼 설명
    - https://www.raspberrypi.org/documentation/configuration/uart.md
  - BT 사용 안함 설정
    - sudo vim /boot/config.txt
    - enable_uart=1
    - dtoverlay=pi3-disable-bt
# GPIO 사용 권한
- sudo usermod -a -G gpio pi
- pi 유저에게 GPIO 사용 권한 허가
