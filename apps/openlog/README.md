# OPENLOG

오픈소스 하드웨어 OpenLog 를 사용하여, 마이크로SD 카드에 시리얼 로그를 저장한다.



## Hardware

<img src="https://user-images.githubusercontent.com/4587330/213354776-15a24575-7202-44db-be2b-a65b826e6e16.png" />



## Software

명령어`rpi_cpu_temp` 는 [Raspberry Pi Monitor]([BerePi/apps/raspberrypi_monitor at master · jeonghoonkang/BerePi · GitHub](https://github.com/jeonghoonkang/BerePi/tree/master/apps/raspberrypi_monitor)) 참고



샘플코드

```python
#!/usr/bin/env python
import subprocess
import time
import serial

ser = serial.Serial(
        port='/dev/ttyAMA0',
        baudrate = 9600,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        bytesize=serial.EIGHTBITS,
        timeout=1
)

while 1:
        temp = subprocess.check_output(['rpi_cpu_temp'], shell=True)
        read_temp = b"%s" % temp
        print(read_temp)
        ser.write(read_temp)
        time.sleep(10)

```






