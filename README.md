## BerePi
supports Raspbian Jessie (ver 2016.04.30), with RaspBerryPi3

#### Wiki
  - OS installation and setup to run fort the SDH sensors
  - It shows basic installation process for Raspi Sensor
    - [BerePi Wiki](https://github.com/jeonghoonkang/BerePi/wiki)
  - Installation Image for RaspberryPi3 (2018.08)
    - http://tinyos.asuscomm.com:2081/open/2018_08_hawaii.zip

##### People
  - Jeonghoon Kang (https://github.com/jeonghoonkang), Wonsik Ko (https://github.com/kowonsik), Philman Jeong(https://github.com/ipmstyle), Sukun Kim (https://github.com/sukunkim)

#### Wireless Sensor Network (WSN) using RaspberryPi 

You can connect wireless sensors to your cyber space easily, just trying to add BerePi module sensor, to your RaspberryPi.
BerePi project opens software which using BerePi hardware modules. 

  - Simple LED video 01 ( YouTube : https://youtu.be/ygJ3qMiGQvw )
  - BereCO2 HW module 
  - BereCO2 update with enclosure
    - ![BereCO2 Enclosure](https://raw.githubusercontent.com/jeonghoonkang/BerePi/master/files/CO2/CO2_inside_01.JPG)
    - ![BereCO2 Enclosure](https://raw.githubusercontent.com/jeonghoonkang/BerePi/master/files/CO2/CO2_inside_02.JPG)
- [Previous Enclosure](https://github.com/jeonghoonkang/BerePi/blob/master/files/RPi2_case.png)
  - BereCO2 update with SHT20 (KETI motes sensor board)
   - SHT20 board photo and connection : (https://raw.githubusercontent.com/jeonghoonkang/BerePi/master/files/Raspi_temp_humi_sht20_keti_motes_bd_00.jpg), (https://raw.githubusercontent.com/jeonghoonkang/BerePi/master/files/Raspi_temp_humi_sht20_keti_motes_bd_01.jpg)
     
## Installation
  - Please follow Wiki(https://github.com/jeonghoonkang/BerePi/wiki) to download and install pre-configured SD image 
  - Old Installation note
    - Download OS image and set up scripts and environemnt, automatically
    - https://github.com/jeonghoonkang/BerePi/blob/master/Install_Raspi_OS.md

## Links

 - additional nice works :
  1. http://www.raspberrypi-spy.co.uk/
  1. http://www.raspberrypi-spy.co.uk/berryclip-6-led-add-on-board/berryclip-6-led-add-on-board-instructions/
 
- If you want to setup BerePi with your own Ubuntu Linux, please run below shell script files to setup packages, development environment
  - Raspi init setting : same in the installation instruction
    - please use, wget https://raw.githubusercontent.com/jeonghoonkang/BerePi/master/setup/init.sh
     - short URL is https://goo.gl/GDiYfN  
     - It downloads init.sh file
     - download and run : source init.sh
  - Raspi2 PinOut:
    - http://www.element14.com/community/docs/DOC-73950/l/raspberry-pi-2-model-b-gpio-40-pin-block-pinout
 
