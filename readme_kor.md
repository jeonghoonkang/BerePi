## BerePi
##### People
  - Jeonghoon Kang (https://github.com/jeonghoonkang), Wonsik Ko (https://github.com/kowonsik), Philman Jeongh (), SeongTaek Kim (), Sukun Kim (), and YOU

### Wireless Sensor Network (WSN) using RaspberryPi 

 - 무선센서 네트워크를 라즈베리파이와 BerePi 센서 모듈로 구축할 수 있습니다. BerePi 센서 모듈은 온습도, CO2, CO, DUST 등의 센서 뿐아니라 LED, LCD 등의 주변기기 들도 지원할 예정입니다. 

 - 라즈베리파이2가 출시된 시점에서 라즈베리 하드웨어는 500만개 이상이 판매되었으나, 전반적으로 교육용 컴퓨터로 인식되고 있습니다만, 향후 컴퓨팅 분야 전반에 영향을 줄것으로 기대됩니다.

 - 라즈베리파이는 운영체제의 안정성 확보, 다양한 HW 지원 라이브러리 부터 서버급의 서비스 SW를 지원하는 등 광범위한 범위의 컴퓨팅 분야로 확대되고 있습니다. 확대 적용이 커지기 위해서는 다양한 주변기기가 제공되어서 여러분야에 할용되어야 할 것입니다. 
 
 - BerePi 는 향후 확대될 라즈베리파이 레벨의 컴퓨팅에 사용되는 다양한 주변기기 하드웨어와 분산된 라즈베리 그룹의 컴퓨팅 리소스를 통합하여 제공하는 소프트웨어 개발이 목표입니다.
 

  - Simple LED video 01 ( YouTube : https://youtu.be/ygJ3qMiGQvw )
  - BereCO2 HW module 
    - ![BereCO2 module](https://raw.githubusercontent.com/kowonsik/RPiLogger/master/th-co2-back.png), ![BereCO2 module](https://raw.githubusercontent.com/kowonsik/RPiLogger/master/th-co2.png)
  - BereCO2 update with enclosure
    - ![BereCO2 Enclosure](https://github.com/jeonghoonkang/BerePi/blob/master/files/RPi2_co2.png)
    - (https://github.com/jeonghoonkang/BerePi/blob/master/files/RPi2_case.png)
  - BereCO2 update with SHT20 (KETI motes sensor board)
   - SHT20 board photo and connection : (https://raw.githubusercontent.com/jeonghoonkang/BerePi/master/files/Raspi_temp_humi_sht20_keti_motes_bd_00.jpg), (https://raw.githubusercontent.com/jeonghoonkang/BerePi/master/files/Raspi_temp_humi_sht20_keti_motes_bd_01.jpg)
     
## Installation
  - Download OS image and set up scripts and environemnt, automatically
  - https://github.com/jeonghoonkang/BerePi/blob/master/Install_Raspi_OS.md

## Links
[BerePi at Slack](https://berepi.slack.com/messages/general/)

additional nice works :
  1. http://www.raspberrypi-spy.co.uk/
  1. http://www.raspberrypi-spy.co.uk/berryclip-6-led-add-on-board/berryclip-6-led-add-on-board-instructions/
 
RaspberryPi 
  - Raspi init setting : same in the installation instruction
    - please use, wget https://raw.githubusercontent.com/jeonghoonkang/BerePi/master/setup/init.sh
     - short URL is https://goo.gl/GDiYfN  
     - It downloads init.sh file
     - download and run : source init.sh
  - Raspi2 PinOut:
    - http://www.element14.com/community/docs/DOC-73950/l/raspberry-pi-2-model-b-gpio-40-pin-block-pinout
  
