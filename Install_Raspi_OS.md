## Install Raspi OS
  - Please download below RasberryPi OS - Rapberrian based on 2015 05 05 version
    - http://125.7.128.54:8070/wordpress/pub/devel/raspi/raspi_8G_2015_0531.zip
    - Unzip it and write img file to SD card
    - if you using more size than 8 GB SD Card, run sudo raspi-config and expand SD memory size
    - check by "df -h", whether you are using full of SD memory size which you want.
    - efficient using smaller size of image file rather than over 16GB image, to reduce download, writing time.
  - After installation BerePi supports automatic installation of Python packages and shell config settting
    - if you have "init.sh" file in '/home/pi', just "source init.sh"
    - otherwise, use " wget http://125.7.128.54:8070/wordpress/pub/init.sh" to download installation script.
    - and just "source init.sh"
  - id / password : pi / tinyos, it has sudo permission
   
  
