## 센서 종류
1. 샤프
2. 하니웰

## 하니웰 드라이버
1. https://github.com/bfaliszek/Python-HPMA115S0/blob/master/Read.py

### Data Sheet
  - https://www.sparkfun.com/datasheets/Sensors/gp2y1010au_e.pdf
  - http://www.sharp-world.com/products/device-china/lineup/data/pdf/datasheet/gp2y1010au_appl_e.pdf

### To use WiringPi
#### update the GPIO

```
==================================================
gp2y1010au0f dust sensor lib
==================================================
= Copyright (c) Davide Gironi, 2012              =
= http://davidegironi.blogspot.it/               =
==================================================


GP2Y1010AU0F is a dust sensor by optical sensing system. 
An infrared emitting diode (IRED) detects the reflected light of dust in air.
This library implements a way to read the signal output from this sensor and
convert it to ug/m^3.


Devel Notes
-----------
This library was developed on Eclipse, built with avr-gcc on Atmega8 @ 8MHz.


License
-------
Please refer to LICENSE file for licensing information.
```


### 참고 crontab
<pre>
*/5 * * * * bash /home/pi/devel/Raspberry_SensorKit/apps/Sensor/DustSensor/run.sh > /home/pi/devel/log/crontab.dust.log 2>&1 

*/33 * * * * bash /home/pi/devel/BerePi/apps/tinyosGW/run_public_ip_rpi.sh <URL> <PORT> <ID> <PASS> > /home/pi/devel/log/crontab.gw.log 2>&1

*/33 * * * * sshpass -p<PASS> scp -o StrictHostKeyChecking=no  /home/pi/devel/BerePi/logs/berelogger.log <ID>@<URL>:www/sensor/dust_home_sensor.log > /home/pi/devel/log/crontab.dust.cp.log 2>&1


*/3 * * * * python3 /home/pi/devel/pir2pi/beating/telegram_report.py 30 > /home/pi/devel/pir2pi/beating/err.log 2>&1 

</pre>



<pre>2025-01-27 06:21:02 [INFO]  PM0.1 Dust 4  ug/m3 
2025-01-27 06:21:02 [INFO]  PM2.5 Dust 6 (50 is bad limit) ug/m3 
2025-01-27 06:21:02 [INFO]  PM10 Dust 7 (100 is bad limit) ug/m3 </pre>
