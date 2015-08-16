
## SHT2x driver for Raspi##
Desc : Temperature & Humidity sensor

 - Setup : install pythong smbus package (I2C lib, you can see below instruction in detail)
 - Check HW connection : ``sudo i2cdetect 1`` it will show something on the printout, commonly 0x40 is SHT2x
 - How to Run : just type `` python sht20.py``

![sht20 image](http://www.sensirion.com/fileadmin/user_upload/customers/sensirion/Bilder/ProductPictures/Sensirion_Humidity_SHT20.jpg)

  - Datasheet : http://www.sensirion.com/fileadmin/user_upload/customers/sensirion/Dokumente/Humidity/Sensirion_Humidity_SHT20_Datasheet_V3.pdf

use with "RASPI HT-CO2 Sensor" (<-to be update)
![RASPI-HTCO2-Sensor](https://raw.githubusercontent.com/kowonsik/RPiLogger/master/th-co2.png)

###  I2C enable for raspberry pi 2 ###

1. install I2C package (It's include BerePi install script)
<pre>
sudo apt-get install python-smbus
sudo apt-get install i2c-tools
</pre>

2. enable I2C config (with Raspi-config)
![raspi-config_run](https://learn.adafruit.com/system/assets/assets/000/022/831/medium800/learn_raspberry_pi_advancedopt.png)
![raspi-config_choose_I2C](https://learn.adafruit.com/system/assets/assets/000/022/832/medium800/learn_raspberry_pi_i2c.png)
![raspi-config_](https://learn.adafruit.com/system/assets/assets/000/022/834/medium800/learn_raspberry_pi_wouldyoukindly.png)
![raspi-config1](https://learn.adafruit.com/system/assets/assets/000/022/833/medium800/learn_raspberry_pi_i2ckernel.png)

3. Edit modules file
<pre> sudo nano /etc/modules</pre>

add 2-lines to the end of /etc/modules file
<pre>
i2c-bcm2708
i2c-dev
</pre>

like this

![/etc/modules/](https://learn.adafruit.com/system/assets/assets/000/003/054/medium800/learn_raspberry_pi_editing_modules_file.png)

#### Test
  - sudo i2cdetect -y 1
  - you should see i2c table (https://learn.adafruit.com/assets/3055)

#### Links 
- [adafruit link](https://learn.adafruit.com/adafruits-raspberry-pi-lesson-4-gpio-setup/configuring-i2c)

#### Photos
- SHT20 interface with Add-on Board - Blue wire-SDA, Yellow wire-SCL, Red-3.3V, Black-GND
 - ![SHT20 interface with Add-on Board](https://raw.githubusercontent.com/jeonghoonkang/BerePi/master/files/raspi_temp_humi_addon.jpg)
- https://github.com/jeonghoonkang/BerePi/blob/master/files/Raspi_temp_humi_sht20_keti_motes_bd_00.jpg
- https://github.com/jeonghoonkang/BerePi/blob/master/files/Raspi_temp_humi_sht20_keti_motes_bd_01.jpg

