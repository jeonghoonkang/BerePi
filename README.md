## BerePi (Bere+RaspberryPi) software for automated computing 
- Big Data collection and analytics software tools based on RaspberryPi which is from IoT level computing system
- Software stack for physical computing and intelligent SW service based on IoT data collection & processing (Big data)
- Based on RaspberryPi distribution (hardware and software)
- supports Ubuntu64_ARM
  - previous version : Raspbian OS, Buster (ver 2019.09.12), with RaspBerryPi4 (input hangul mode, 한글모드)
  - now you can use Ubuntu with SSD booting via USB
  
##### By Contribution
  - Jeonghoon Kang(https://github.com/jeonghoonkang), Philman Jeong(https://github.com/ipmstyle), Sukun Kim(https://github.com/sukunkim)

### BerePi with SSD(Disk Pi) which is a new direction for secure pi computing
- After 2021, not long ago, RaspberryPi started to support SSD/HDD Booting by USB link. It gives us a new approach which has a very quick booting speed and secure, nice non-breakable booting code, rather than beaten by electricity accident such as SD card crash.
- more detail new hardware, please visit https://polarized-poppyseed-8e0.notion.site/0c68de4668d74bb58c526406ec78d47d

### Old documents which is still valid.

#### Wiki doc
  - RaspberryPi OS installation and setup to run the SDH sensors
  - It shows basic installation process for Raspberyypi Sensor System
    - [BerePi Wiki](https://github.com/jeonghoonkang/BerePi/wiki)
  - Installation Image for RaspberryPi4 (2020.08)
    - RaspberryPi image install (use your computer to copy raspberrypi OS in SD card)
      - https://www.raspberrypi.org/downloads/
    - important first setup check steps:
      1. use American English language, US keyboard, US timezone (like LA)
      2. change hostname by editing /etc/hostname (like tinygw-4b-0820-31)
      3. raspberrypi config run to setup SSH connection
    - if you want to install Ubuntu 64-bit, follow the instruction, it needs 8G sd card.

#### Wireless Sensor Network (WSN) using RaspberryPi 
You can connect wireless sensors to your cyber space easily, just trying to add BerePi module sensor, to your RaspberryPi. Additionally, BerePi provides SSD storage which gives fast access spped and large storage with cloud computing capability. 
BerePi project supports open software which using BerePi hardware modules. 
  - Self Data Machine 
    - <img width="300" alt="image" src="https://user-images.githubusercontent.com/4180063/221742941-657e6240-818a-4c00-b5e8-f3b6f8d0b10d.png">  <img width="315" alt="image" src="https://user-images.githubusercontent.com/4180063/221743531-47abcc0f-6048-48d4-b4f5-cdda79568974.png">
  - Simple LED video 01 (YouTube : https://youtu.be/ygJ3qMiGQvw)
  - BereCO2 HW module   
  - BereCO2 update with enclosure
    - [BereCO2 Enclosure](https://raw.githubusercontent.com/jeonghoonkang/BerePi/master/files/CO2/CO2_inside_01.JPG)
    - [BereCO2 Enclosure](https://raw.githubusercontent.com/jeonghoonkang/BerePi/master/files/CO2/CO2_inside_02.JPG)
- [Previous Enclosure](https://github.com/jeonghoonkang/BerePi/blob/master/files/RPi2_case.png )
  - BereCO2 update with SHT20 (KETI motes sensor board)
   - SHT20 board photo and connection : (https://raw.githubusercontent.com/jeonghoonkang/BerePi/master/files/Raspi_temp_humi_sht20_keti_motes_bd_00.jpg), (https://raw.githubusercontent.com/jeonghoonkang/BerePi/master/files/Raspi_temp_humi_sht20_keti_motes_bd_01.jpg)
     
## Installation
  - Please follow Wiki(https://github.com/jeonghoonkang/BerePi/wiki) to download and install pre-configured SD image 
  - Old Installation note
    - Download OS image and set up scripts and environemnt, automatically
    - https://github.com/jeonghoonkang/BerePi/blob/master/Install_Raspi_OS.md

## Links
 - nice additional external works :
  1. http://www.raspberrypi-spy.co.uk/
  1. http://www.raspberrypi-spy.co.uk/berryclip-6-led-add-on-board/berryclip-6-led-add-on-board-instructions/
 
- If you want to setup BerePi with your own Ubuntu Linux, please run below shell script files to setup packages, development environment
  - Raspi init setting : same in the installation instruction
    - please use, wget https://raw.githubusercontent.com/jeonghoonkang/BerePi/master/setup/init.sh
     - short URL is https://goo.gl/GDiYfN  
     - It downloads init.sh file
     - download and run : source init.sh
  - Raspi2 PinOut:http://www.element14.com/community/docs/DOC-73950/l/raspberry-pi-2-model-b-gpio-40-pin-block-pinout
 
