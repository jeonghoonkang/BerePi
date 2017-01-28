#### Installation, Raspi OS 
  - Please download below RasberryPi OS - Rapberrian based on 2016 01 Jessie version
    - http://cogcom.asuscomm.com:6080/open/raspi_4G_2016_0112.zip
    - old version
      - http://125.7.128.54:8070/wordpress/pub/devel/raspi/raspi_4G_2015_0706.zip
      - http://125.7.128.54:8070/wordpress/pub/devel/raspi/raspi_4G_2016_0430.zip
     - it supports Korean Lang. with common US keyboard, timezone is SEOUL, I2C enabled  
    - Unzip it and write img file to SD card
    - if you using more size than 8 GB SD Card, run sudo raspi-config and expand SD memory size
    - check by "df -h", whether you are using full of SD memory size which you want.
    - efficient using smaller size of image file rather than over 16GB image, to reduce download, writing time.
  - After installation BerePi supports automatic installation of Python packages and shell config settting
    - if you have "init.sh" file in '/home/pi', just "source init.sh"
    - otherwise, use " wget https://raw.githubusercontent.com/jeonghoonkang/BerePi/master/setup/init.sh" to download installation script.
    - and just "source init.sh"
  - id / password : pi / tinyos, it has sudo permission

#### Setup shell environment and packages
  - download shell script from https://raw.githubusercontent.com/jeonghoonkang/BerePi/master/setup/init.sh (https://goo.gl/GDiYfN) or http://125.7.128.54:8070/wordpress/pub/init.sh
    - wget https://raw.githubusercontent.com/jeonghoonkang/BerePi/master/setup/init.sh
  - and just run 'source init.sh'
    - Be carefull that init.sh will change your /etc/rc.local, /etc/resolv, /etc/network/interfaces
    - If you just want update SW package installation, look into the file init.sh, which has setup_apt.sh process, you will be able to easily catch the path
  
