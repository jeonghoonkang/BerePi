# OPENLOG

- 소개 : **저렴한 가격**(메모리 포함 2만원 이내)으로 추가되는 **데이터로거** <br />
         (2023년 기준, 알리 개당 4천원)
- 기능 : 오픈소스 하드웨어 OpenLog 를 사용하여, 마이크로SD 카드에 시리얼 로그를 저장한다.

- [OpenLog 정보](https://silky-sundial-174.notion.site/OPENLOG-1054fe19c62e499b837b049489d8066c) Notion 링크



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
